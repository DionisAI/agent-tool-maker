"""Explicit privileged Linux acceptance; NOT part of the default pytest suite.

Run only in an isolated test runner as root, with a readable installed ATM package.
Creates no system accounts/groups; a child drops to nobody (65534). No supplier IO.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading

from agent_tool_maker.broker import Broker, grant
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault


def test_distinct_uid_can_execute_but_cannot_read_vault():
    assert sys.platform.startswith('linux') and os.geteuid()==0, 'Explicit root Linux test required; do not count a skip as acceptance.'
    assert hasattr(socket,'SO_PEERCRED')
    with tempfile.TemporaryDirectory(prefix='atm-uid-') as rootdir:
        root=Path(rootdir);root.chmod(0o755)
        state=State(root/'owner');v=Vault(state,password='fake-long-uid-test');v.init('passphrase');v.put('fal','FAKE-NOT-A-PRODUCTION-KEY')
        runtime=root/'run';runtime.mkdir(mode=0o750);os.chown(runtime,-1,65534)
        workspace=root/'project';workspace.mkdir(mode=0o770);os.chown(workspace,-1,65534)
        shutil.copy(Path(__file__).parent.parent/'tests/fixtures/tone.wav',workspace/'tone.wav')
        owner=Router(state.home,vault=v);bind_cli(state,'ffprobe',shutil.which('ffprobe'))
        server=Broker(state.home,vault=v,socket_file=runtime/'broker.sock',socket_group=65534)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            profile=root/'nobody.json'
            grant(owner,'separate-user',tools=['ffmpeg.probe'],workspace=workspace,output=profile,
                  socket_file=server.path,client_uid=65534,socket_group=65534,apply=True)
            os.chown(profile,65534,65534)
            code='''import json,sys\nfrom pathlib import Path\nfrom agent_tool_maker.broker import call\ntry:\n Path(sys.argv[2]).read_bytes()\n raise AssertionError("agent read private vault")\nexcept PermissionError:pass\nr=call(Path(sys.argv[1]),'run',{'tool':'ffmpeg.probe','inputs':{'path':'tone.wav'},'workspace':sys.argv[3],'request_key':'uid-test'})\nassert r['status']=='completed',r\nprint(json.dumps({'completed':True,'vault_read_denied':True}))'''
            child=subprocess.run([sys.executable,'-c',code,str(profile),str(state.path),str(workspace)],
                user=65534,group=65534,extra_groups=[],cwd='/tmp',stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
            assert child.returncode==0,child.stdout+child.stderr
            assert json.loads(child.stdout)=={'completed':True,'vault_read_denied':True}
            cfg=json.loads(profile.read_text())
            # The same bearer used by another UID is denied by SO_PEERCRED, even root.
            request={k:cfg[k] for k in ['id','token']};request.update(operation='status',args={})
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                conn.connect(str(server.path));conn.sendall(json.dumps(request).encode()+b'\n')
                reply=json.loads(conn.makefile('rb').readline())
            assert reply['error']['code']=='peer_uid_denied'
        finally:
            server.shutdown();thread.join(10);server.server_close();owner.close()
