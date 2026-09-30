"""Offline multi-device + fresh-session demo. Only fake keys, no supplier calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave

from agent_tool_maker.broker import Broker, grant
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.sync import Sync, write_sync_file
from agent_tool_maker.vault import Vault


def demo() -> dict:
    ffprobe=shutil.which('ffprobe')
    if not ffprobe: raise RuntimeError('Install FFprobe for the real local execution tier; this demo does not fake it.')
    with tempfile.TemporaryDirectory(prefix='atm-demo-') as temp:
        root=Path(temp);nodes=[]
        for label in ['laptop','server']:
            vault=Vault(State(root/label),password='DEMO-ONLY-NOT-A-REAL-PASSWORD')
            vault.init('passphrase');sync=Sync(vault);sync.initialize(label);nodes.append(sync)
        a,b=nodes
        for x,y in [(a,b),(b,a)]:x.trust(y.identity(),y.identity()['id'],send=['fal'],receive=['fal'],apply=True)
        a.vault.put('fal','DEMO-FAKE-KEY-BASE')
        packet=a.export_packet(b.identity()['id']);raw=canonical(packet).encode()
        assert b'DEMO-FAKE-KEY-BASE' not in raw
        write_sync_file(root/'transfer.atmsync',raw)
        b.import_packet(packet,apply=True)
        assert a.vault.unlock()!=b.vault.unlock() and b.vault.get('fal')=='DEMO-FAKE-KEY-BASE'
        a.vault.put('fal','DEMO-FAKE-KEY-LEFT');b.vault.put('fal','DEMO-FAKE-KEY-RIGHT')
        b.import_packet(a.export_packet(b.identity()['id']),apply=True)
        row=b.status()['records'][0];assert row['state']=='conflict'
        chosen=next(v for v in row['heads'] if v['author']==a.identity()['id'])
        b.resolve('fal',chosen['revision'],row['expected'],apply=True)
        a.import_packet(b.export_packet(a.identity()['id']),apply=True)
        assert a.vault.get('fal')==b.vault.get('fal')=='DEMO-FAKE-KEY-LEFT'
        project=root/'project';project.mkdir()
        with wave.open(str(project/'tone.wav'),'wb') as f:
            f.setparams((1,2,8000,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(1000*math.sin(i*2*math.pi*440/8000))) for i in range(6400)))
        (project/'input.json').write_text('{"path":"tone.wav"}')
        owner=Router(b.state.home,vault=b.vault);bind_cli(owner.state,'ffprobe',ffprobe)
        server=Broker(owner.state.home,socket_file=root/'broker.sock',vault=b.vault)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            profile=root/'client.json'
            grant(owner,'claude',tools=['ffmpeg.probe'],workspace=project,output=profile,socket_file=server.path,apply=True)
            env={k:v for k,v in os.environ.items() if not any(word in k for word in ['TOKEN','API_KEY','VAULT_PASSWORD'])}
            calls=[]
            for _ in range(2):
                run=subprocess.run([sys.executable,'-m','agent_tool_maker','--client-profile',str(profile),'run','ffmpeg.probe',
                    '--input',str(project/'input.json'),'--workspace',str(project),'--request-key','same-logical-task'],
                    env=env,stdin=subprocess.DEVNULL,cwd=project,text=True,capture_output=True,timeout=30)
                if run.returncode:raise RuntimeError('Demo CLI failed; no output containing secrets is included.')
                calls.append(json.loads(run.stdout))
            assert all(c['status']=='completed' for c in calls) and calls[0]['id']==calls[1]['id']
            return {'demo':True,'supplier_requests':0,'supplier_spend_usd':0,'devices':2,
                    'encrypted_packet_sha256':hashlib.sha256(raw).hexdigest(),
                    'distinct_local_keys':True,'concurrent_edit':'blocked_then_explicitly_resolved',
                    'fresh_agent_processes':2,'actual_ffprobe_jobs':len(owner.state.jobs()),
                    'same_task_not_resubmitted':True,'real_os_keyring_tested':False,
                    'temporary_secret_stores_deleted_on_exit':True}
        finally:
            server.shutdown();thread.join(10);server.server_close();owner.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path)
    args=parser.parse_args();result=demo();text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:
        if args.out.exists():raise SystemExit('Output exists; choose a new receipt path.')
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(text+'\n')
    print(text)
