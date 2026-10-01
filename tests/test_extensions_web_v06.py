import json
from agent_tool_maker.extensions import new_template
from agent_tool_maker.engine import Router
from agent_tool_maker.storage import canonical
from test_webapp_v04 import console,get,post


def test_workshop_requires_auth_and_never_executes(console):
    s,c=console
    assert c.get('/api/extensions').status_code==401
    assert get(console,'/api/extensions').json()['custom_tools']==[]
    for endpoint in ['draft','run','login','shell']:
        assert post(console,'/api/extensions/'+endpoint,{}).status_code==404


def test_web_declare_then_write_new_key(console):
    name='unknown.brand'
    assert post(console,'/api/credentials/declare',{'name':name}).json()['action']=='declare'
    assert not any(x['provider']==name for x in get(console,'/api/connections').json()['connections'])
    assert post(console,'/api/credentials/declare',{'name':name,'apply':True}).status_code==200
    assert post(console,'/api/vault/init',{'backend':'passphrase','passphrase':'TEST-ONLY-long-password'}).status_code==200
    r=post(console,'/api/connections/save',{'provider':name,'value':'FAKE-unknown-key','passphrase':'TEST-ONLY-long-password'})
    assert r.status_code==200 and r.json()['saved_encrypted']
    assert 'FAKE-unknown-key' not in r.text+get(console,'/api/extensions').text+get(console,'/api/connections').text


def test_web_extension_preview_install_update_cas(console):
    t=new_template('custom.web','web',url='https://example.com/')
    p=post(console,'/api/extensions/validate',{'manifest':t});assert p.status_code==200,p.text
    sha=p.json()['sha256'];assert 'external_write' in p.json()['permissions']
    assert get(console,'/api/extensions').json()['custom_tools']==[]
    assert post(console,'/api/extensions/install',{'manifest':t,'approved_sha256':'bad'}).status_code==400
    r=post(console,'/api/extensions/install',{'manifest':t,'approved_sha256':sha});assert r.status_code==200,r.text
    changed={**t,'title':'New title'}
    plan=post(console,'/api/extensions/validate',{'manifest':changed}).json()
    assert plan['previous_sha256']==sha and plan['action']=='update'
    assert post(console,'/api/extensions/install',{'manifest':changed,'approved_sha256':plan['sha256'],'expected_sha256':'bad'}).status_code==400
    assert post(console,'/api/extensions/install',{'manifest':changed,'approved_sha256':plan['sha256'],'expected_sha256':sha}).status_code==200
    fresh=Router(console[0].home)
    try:
        assert fresh.catalog.get('custom.web')['title']=='New title'
        assert not fresh.state.jobs() and not fresh.state.secret_names()
    finally:fresh.close()


def test_web_cannot_replace_builtins_or_send_commands(console):
    t=new_template('fal.generate','web',url='https://example.com/')
    assert post(console,'/api/extensions/validate',{'manifest':t}).status_code==400
    assert post(console,'/api/extensions/validate',{'manifest':{},'shell':'whoami'}).status_code==400
    assert post(console,'/api/credentials/declare',{'name':'../../vault','apply':True}).status_code==400
