import json
from pathlib import Path
import pytest
from agent_tool_maker.extensions import new_template, update_manifest
from agent_tool_maker.maker import digest
from agent_tool_maker.errors import RouterError
from agent_tool_maker.broker import grant,call
from test_broker_v05 import broker_env
from test_extensions_v06 import add


def test_browser_recipe_scopes_pin_after_update(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    tool,path=add(owner,new_template('custom.web','web',url='https://example.com/'),tmp_path)
    profile=tmp_path/'profile.json'
    grant(owner,'claude',tools=[tool['id']],workspace=workspace,output=profile,socket_file=server.path,
          grants=['external_write'],allow_paid=True,apply=True)
    result=call(profile,'run',{'tool':tool['id'],'inputs':{},'workspace':str(workspace),'request_key':'preview','dry_run':True,'expect_definition':digest(tool)})
    assert result['dry_run'] and not owner.state.jobs()
    modified={**tool,'title':'Revised definition'};path.write_text(json.dumps(modified))
    update_manifest(owner.state,owner.catalog,path,approval=digest(modified),expected=digest(tool))
    with pytest.raises(RouterError) as e:call(profile,'describe',{'tool':tool['id']})
    assert e.value.code=='grant_stale'


def test_generated_cli_digest_checked_in_broker(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    tool,path=add(owner,new_template('custom.web','web',url='https://example.com/'),tmp_path)
    profile=tmp_path/'profile.json'
    grant(owner,'codex',tools=[tool['id']],workspace=workspace,output=profile,socket_file=server.path,
          grants=['external_write'],allow_paid=True,apply=True)
    with pytest.raises(RouterError) as e:
        call(profile,'run',{'tool':tool['id'],'inputs':{},'workspace':str(workspace),'request_key':'preview','dry_run':True,'expect_definition':'bad'})
    assert e.value.code=='definition_changed'
    assert not owner.state.jobs()
