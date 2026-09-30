#!/usr/bin/env python3
"""Executable acceptance: no manifests, fake credentials, actual PTY/socket/HTTP/processes.

No real model/vendor account. Two device stores below are on ONE test machine.
Output records facts, not raw profiles, passwords, keys, headers or child env.
"""
from __future__ import annotations
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from agent_tool_maker.engine import Router
from agent_tool_maker.secrets_provider import permit_exec
from agent_tool_maker.storage import State
from agent_tool_maker.sync import Sync
from agent_tool_maker.vault import Vault


def clean_env():
    return {k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('KEY','SECRET','TOKEN','PASSWORD'))}


def start(atm, home, password, ttl='30m'):
    master, slave = pty.openpty()
    proc = subprocess.Popen([atm,'--home',str(home),'unlock','--ttl',ttl], stdin=slave, stdout=slave,
                            stderr=slave, env=clean_env(), start_new_session=True)
    os.close(slave)
    data=b'';sent=False;end=time.monotonic()+20
    try:
        while time.monotonic()<end:
            if select.select([master],[],[],.2)[0]:
                chunk=os.read(master,65536);data+=chunk
                if b'Vault passphrase: ' in data and not sent:
                    os.write(master,password.encode()+b'\n');sent=True
                for line in data.splitlines():
                    if line.startswith(b'{'):
                        obj=json.loads(line)
                        if obj.get('unlocked'):
                            assert sent and data.count(b'Vault passphrase: ')==1
                            assert password.encode() not in data
                            return proc,master,obj
            if proc.poll() is not None:break
        raise AssertionError('A foreground session did not start successfully; no secret-bearing output is printed.')
    except BaseException:
        proc.terminate();proc.wait(timeout=5);os.close(master);raise


def cli(atm, args, *, cwd=None):
    proc=subprocess.run([atm,*args],stdin=subprocess.DEVNULL,capture_output=True,text=True,
                        env=clean_env(),cwd=cwd,timeout=40)
    result=json.loads(proc.stdout)
    return proc.returncode,result


def demo():
    atm=shutil.which('atm');assert atm,'Install the reviewed source first.'
    receipt={'version':'0.7.0','real_model_calls':0,'real_vendor_calls':0,'fake_credentials':True,
             'two_stores_on_one_machine':True,'native_keyring_tested':False,'real_agent_hosts_tested':False}
    with tempfile.TemporaryDirectory(prefix='atm7-demo-') as td:
        root=Path(td);password='fake-password-for-this-test';key='fake-acceptance-'+os.urandom(16).hex()
        r=Router(root/'a');r.vault=Vault(r.state,password=password);r.vault.init('passphrase');r.vault.put('fal',key)
        # Actual local HTTP target that verifies the header, never logs it.
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                okay=self.headers.get('X-Test-Key')==key;calls.append(okay)
                raw=json.dumps({'authorized':okay}).encode()
                self.send_response(200 if okay else 401);self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        ht=threading.Thread(target=http.serve_forever,daemon=True);ht.start()
        project=root/'project';project.mkdir()
        (project/'app.py').write_text('import os,urllib.request\n'
            f'req=urllib.request.Request("http://127.0.0.1:{http.server_port}/",headers={{"X-Test-Key":os.environ["FAL_KEY"]}})\n'
            'with urllib.request.urlopen(req,timeout=5) as r:print(r.read().decode())\n')
        scopes=[]
        for agent in ('claude','codex'):
            opts=dict(mappings=['FAL_KEY=atm://fal'],argv=[sys.executable,'app.py'],workspace=project,output=root/(agent+'.json'))
            plan=permit_exec(r,agent,**opts)
            result=permit_exec(r,agent,**opts,apply=True,approve=plan['sha256']);scopes.append(Path(result['profile']))
        receipt['no_manifest_created']=not any(project.glob('*.json'))
        proc,master,started=start(atm,r.state.home,password)
        try:
            receipt['one_password_prompt']=True
            receipt['lease_seconds_at_start']=started['seconds_remaining']
            assert 1790<=started['seconds_remaining']<=1800
            outputs=[]
            for i,p in enumerate(scopes):
                code,found=cli(atm,['--client-profile',str(p),'keys','find','FAL_KEY'],cwd=project)
                assert code==0 and found['matches'][0]['name']=='fal'
                code,value=cli(atm,['--client-profile',str(p),'exec','--env','FAL_KEY=atm://fal',
                    '--workspace',str(project),'--request-key',f'session-{i}','--',sys.executable,'app.py'],cwd=project)
                assert code==0 and json.loads(value['stdout'])=={'authorized':True}
                assert key not in json.dumps(value) and password not in json.dumps(value)
                outputs.append({'client_label':('claude','codex')[i],'status':value['status'],'returncode':value['returncode']})
            receipt['independent_headless_clients']=outputs
            assert calls==[True,True]
            receipt['local_http_authenticated_calls']=len(calls)
            assert not list(project.glob('.env*'))
            assert key.encode() not in r.state.path.read_bytes()
            receipt['no_plaintext_env_or_state']=True
            # Re-running unlock never reads stdin or extends a running lease.
            code,unchanged=cli(atm,['--home',str(r.state.home),'unlock','--ttl','1h'])
            assert code==0 and unchanged['action']=='unchanged' and unchanged['seconds_remaining']<=started['seconds_remaining']
            receipt['repeat_unlock_does_not_prompt_or_extend']=True
            code,locked=cli(atm,['--home',str(r.state.home),'lock']);assert code==0 and not locked['unlocked']
            proc.wait(timeout=20)
            code,denied=cli(atm,['--client-profile',str(scopes[0]),'exec','--env','FAL_KEY=atm://fal',
                '--workspace',str(project),'--','/bin/echo','no'])
            assert code!=0
            receipt['lock_denies_without_fallback']=True
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
            os.close(master)
        # Sync only encrypted credential records to a second independent vault.
        vb=Vault(State(root/'b'),password='fake-second-device-password');vb.init('passphrase')
        sa,sb=Sync(r.vault),Sync(vb);sa.initialize('fixture-a');sb.initialize('fixture-b')
        a,b=sa.identity(),sb.identity()
        sa.trust(b,b['id'],send=['fal'],apply=True);sb.trust(a,a['id'],receive=['fal'],apply=True)
        packet=sa.export_packet(b['id']);assert key not in json.dumps(packet)
        sb.import_packet(packet,apply=True);assert vb.get('fal')==key
        assert r.vault.unlock()!=vb.unlock()
        receipt['separate_master_keys_encrypted_transfer']=True
        # The receiver grants its own scope: neither grants nor sessions were copied.
        rb=Router(vb.state.home,vault=vb)
        opts=dict(mappings=['FAL_KEY=atm://fal'],argv=[sys.executable,'app.py'],workspace=project,output=root/'receiver.json')
        plan=permit_exec(rb,'claude',**opts);permit_exec(rb,'claude',**opts,apply=True,approve=plan['sha256'])
        proc,master,_=start(atm,vb.state.home,'fake-second-device-password')
        try:
            code,value=cli(atm,['--client-profile',str(root/'receiver.json'),'exec','--env','FAL_KEY=atm://fal',
                '--workspace',str(project),'--',sys.executable,'app.py'])
            assert code==0 and json.loads(value['stdout'])=={'authorized':True}
            receipt['receiver_fresh_process_uses_synced_key']=True
            cli(atm,['--home',str(vb.state.home),'lock']);proc.wait(timeout=20)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
            os.close(master);rb.close()
        # Natural expiry is accelerated, NOT presented as a full 30-minute soak.
        proc,master,_=start(atm,r.state.home,password,ttl='2s')
        try:
            proc.wait(timeout=15)
            assert not (r.state.home/'broker.sock').exists()
            receipt['natural_expiry_seconds_tested']=2
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
            os.close(master)
        http.shutdown();ht.join(5);http.server_close();r.close()
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    value=demo();args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(value,ensure_ascii=False,indent=2))
