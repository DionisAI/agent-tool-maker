"""Exercise actual CLI dispatch and private status without any supplier network."""
import json
from pathlib import Path
import pytest
from agent_tool_maker.cli import main


def test_cli_sync_and_access_end_to_end(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('ATM_VAULT_PASSWORD','CLI-FAKE-ONLY-PASSWORD')
    def run(home,*args):
        code=main(['--home',str(home),*map(str,args)]);out=json.loads(capsys.readouterr().out)
        assert code==0,out
        assert 'CLI-FAKE-ONLY-PASSWORD' not in json.dumps(out)
        return out
    a,b=tmp_path/'a',tmp_path/'b'
    for path in (a,b):run(path,'vault','init','--backend','passphrase');run(path,'sync','init','--name',path.name)
    cards=[]
    for path in (a,b):
        card=run(path,'sync','identity');cards.append(card)
        run(path,'sync','identity','--out',tmp_path/(path.name+'.json'))
    run(a,'sync','trust',tmp_path/'b.json','--fingerprint',cards[1]['id'],'--send','fal','--apply')
    run(b,'sync','trust',tmp_path/'a.json','--fingerprint',cards[0]['id'],'--receive','fal','--apply')
    monkeypatch.setenv('EXPLICIT_FAKE_IMPORT','CLI-FAKE-VENDOR-KEY')
    run(a,'connect','fal','--env','EXPLICIT_FAKE_IMPORT')
    monkeypatch.delenv('EXPLICIT_FAKE_IMPORT')
    packet=tmp_path/'p.atmsync';run(a,'sync','export','--to',cards[1]['id'],'--out',packet)
    assert 'CLI-FAKE-VENDOR-KEY' not in packet.read_text()
    run(b,'sync','import',packet);run(b,'sync','import',packet,'--apply')
    assert next(c for c in run(b,'connections','list')['connections'] if c['provider']=='fal')['configured']
    assert run(b,'sync','conflicts')['conflicts']==[]
    run(b,'sync','status');run(b,'sync','exchange','--directory',tmp_path/'shared')
    run(b,'sync','exchange','--directory',tmp_path/'shared','--apply')
    work=tmp_path/'project';work.mkdir();profile=tmp_path/'c.json'
    run(b,'access','grant','--agent','claude','--tool','ffmpeg.probe','--workspace',work,'--out',profile)
    record=run(b,'access','grant','--agent','claude','--tool','ffmpeg.probe','--workspace',work,'--out',profile,'--apply')
    assert run(b,'access','list')['grants'][0]['id']==record['id']
    run(b,'access','revoke',record['id'],'--apply');run(b,'broker','status')
    run(a,'sync','revoke',cards[1]['id'],'--apply')


@pytest.mark.parametrize('args',[['sync','status'],['access','list']])
def test_status_does_not_prompt_on_fresh_home(tmp_path,capsys,args):
    assert main(['--home',str(tmp_path/'empty'),*args])==0
    assert json.loads(capsys.readouterr().out)['secrets_returned'] is False
