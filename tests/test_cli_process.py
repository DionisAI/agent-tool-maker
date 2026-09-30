import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from agent_tool_maker.cli_adapter import bind_cli,execute_cli
from agent_tool_maker.errors import RouterError

@pytest.mark.integration
def test_xyq_actual_child_process_lifecycle(router,workspace,assets,tmp_path,monkeypatch):
    binary=tmp_path/'fixture-cli'
    image=base64.b64encode(assets['image.png']).decode()
    binary.write_text(f'''#!{sys.executable}
import sys,json,os,base64
from pathlib import Path
args=sys.argv[1:]
assert 'ELEVENLABS_API_KEY' not in os.environ
assert 'ATM_VAULT_PASSWORD' not in os.environ
if args[0]=='generate-image':
 Path('received-args.json').write_text(json.dumps(args))
 print(json.dumps({{'thread_id':'fixture-thread','run_id':'fixture-run'}}))
elif args[0]=='query-result':
 dest=Path(args[args.index('--download-dir')+1]);dest.mkdir(parents=True,exist_ok=True)
 p=dest/'output.png';p.write_bytes(base64.b64decode('{image}'))
 print(json.dumps({{'completed':True,'images':[{{'output_path':str(p)}}]}}))
else: sys.exit(2)
''')
    binary.chmod(0o700)
    bind_cli(router.state,'xyq',str(binary))
    monkeypatch.setenv('ELEVENLABS_API_KEY','SHOULD_NOT_BE_IN_CHILD')
    monkeypatch.setenv('ATM_VAULT_PASSWORD','SHOULD_NOT_BE_IN_CHILD')
    prompt='hello; touch SHOULD_NOT_EXIST && $(echo injection)'
    j=router.run('xyq.image',{'prompt':prompt,'model':'fixture-model'},workspace,allow_paid=True)
    assert j['status']=='queued',j
    result=router.refresh(j['id'])
    assert result['status']=='completed',result
    assert prompt in json.loads((workspace/'received-args.json').read_text())
    assert not (workspace/'SHOULD_NOT_EXIST').exists()

@pytest.mark.integration
def test_actual_ffmpeg_transcode_and_probe(router,workspace):
    ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe')
    if not ffmpeg or not ffprobe: pytest.skip('ffmpeg/ffprobe not installed')
    bind_cli(router.state,'ffmpeg',ffmpeg);bind_cli(router.state,'ffprobe',ffprobe)
    source=Path(__file__).parent/'fixtures/tone.wav'
    shutil.copyfile(source,workspace/'tone.wav')
    a=router.run('ffmpeg.audio_to_mp3',{'path':'tone.wav'},workspace)
    assert a['status']=='completed',a
    b=router.run('ffmpeg.probe',{'path':a['data']['artifacts'][0]['path']},workspace)
    assert b['status']=='completed',b
    assert float(b['data']['result']['format']['duration'])>0.7
    assert b['data']['result']['streams'][0]['codec_name']=='mp3'

@pytest.mark.integration
def test_timeout_does_not_hang(router,workspace,tmp_path):
    executable=tmp_path/'sleep-cli';executable.write_text(f'#!{sys.executable}\nimport time;time.sleep(10)\n');executable.chmod(0o700)
    bind_cli(router.state,'xyq',str(executable))
    with pytest.raises(RouterError,match='timed out'): execute_cli(router.state,'xyq',[],workspace,timeout=0.1)

@pytest.mark.integration
def test_cli_errors_do_not_echo_stderr(router,workspace,tmp_path):
    executable=tmp_path/'bad-cli';executable.write_text(f'#!{sys.executable}\nimport sys;print("MY-SECRET",file=sys.stderr);sys.exit(2)\n');executable.chmod(0o700)
    bind_cli(router.state,'xyq',str(executable))
    with pytest.raises(RouterError) as error: execute_cli(router.state,'xyq',[],workspace)
    assert 'MY-SECRET' not in str(error.value)


def test_cli_bind_requires_existing_file(router):
    with pytest.raises(RouterError): bind_cli(router.state,'xyq','/not/real/binary')
    with pytest.raises(RouterError): bind_cli(router.state,'arbitrary','/bin/sh')

@pytest.mark.integration
def test_cli_command_interface(tmp_path):
    env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
    home=tmp_path/'home'
    base=[sys.executable,'-m','agent_tool_maker','--home',str(home)]
    def call(*args,input=None):
        return subprocess.run(base+list(args),input=input,text=True,capture_output=True,env=env,timeout=20)
    r=call('init');assert r.returncode==0 and json.loads(r.stdout)['tools']>=150
    r=call('describe','tripo.web');assert json.loads(r.stdout)['implementation']=='browser'
    r=call('run','tripo.text_to_3d','--input','-','--dry-run',input='{"prompt":"robot"}')
    assert r.returncode==0 and json.loads(r.stdout)['network_calls']==0
    r=call('run','tripo.text_to_3d','--input','-',input='{"prompt":"robot"}')
    assert r.returncode==2 and json.loads(r.stdout)['error']['code']=='paid_confirmation_required'
    r=call('skill','export','--destination',str(tmp_path/'skills'))
    assert r.returncode==0
    assert (tmp_path/'skills/agent-tool-maker/SKILL.md').exists()
    assert call('skill','export','--destination',str(tmp_path/'skills')).returncode==2

@pytest.mark.integration
def test_cli_missing_input_structured_error(tmp_path):
    from agent_tool_maker.cli import load_input
    with pytest.raises(RouterError): load_input(str(tmp_path/'missing.json'))
