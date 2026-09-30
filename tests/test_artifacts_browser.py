import json
import struct
from pathlib import Path
import pytest
from agent_tool_maker.artifacts import validate_bytes,save_artifact,confined_file,managed_dir
from agent_tool_maker.errors import RouterError

@pytest.mark.parametrize('name',['image.png','tone.mp3','model.glb'])
def test_fixture_validation(assets,name):
    result=validate_bytes(assets[name],Path(name).suffix)
    assert result['semantic_quality_checked'] is False

@pytest.mark.parametrize('data,suffix',[(b'','.png'),(b'<html>login page</html>','.png'),(b'fake','.glb'),
 (b'not json','.json'),(b'1234567890123456','.mp4'),(b'xx','.mp3'),(b'x','.exe'),
 (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>','.svg'),
 (b'<svg onload="x"/>','.svg'),(b'<svg><image href="https://evil.test/a"/></svg>','.svg')])
def test_invalid_files(data,suffix):
    with pytest.raises(RouterError): validate_bytes(data,suffix)


def test_glb_length_tampering(assets):
    data=bytearray(assets['model.glb']);struct.pack_into('<I',data,8,len(data)+4)
    with pytest.raises(RouterError): validate_bytes(bytes(data),'.glb')


def test_file_hash_and_scope(router,workspace,assets,tmp_path):
    job=router.run('tripo.web',{'task':'cube'},workspace)
    artifact=save_artifact(workspace,job['id'],assets['model.glb'],hint='model.glb')
    assert Path(artifact['path']).is_relative_to(workspace)
    outside=tmp_path/'outside.glb';outside.write_bytes(assets['model.glb'])
    with pytest.raises(RouterError): confined_file(workspace,str(outside))
    link=workspace/'link.glb';link.symlink_to(outside)
    with pytest.raises(RouterError): confined_file(workspace,'link.glb')


def test_managed_symlink_rejected(router,workspace,tmp_path):
    (workspace/'.atm').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(RouterError): managed_dir(workspace,'12345678-1234-1234-1234-123456789012')


def test_handoff_is_not_execution(router,workspace,fixture_provider):
    job=router.run('tripo.web',{'task':'Create a low-poly chair.'},workspace)
    assert job['status']=='requires_browser'
    h=job['data']['handoff']
    assert h['execution']=='delegated_to_host_agent'
    assert h['entry_url']=='https://studio.tripo3d.ai/'
    assert job['data']['artifacts']==[] and fixture_provider.calls==[]
    assert 'cookie' in h['credential_policy']


def test_browser_completion_requires_actual_files(router,workspace,assets):
    job=router.run('tripo.web',{'task':'chair'},workspace)
    with pytest.raises(RouterError): router.complete_browser(job['id'],['missing.glb'],'https://studio.tripo3d.ai/task/123')
    assert router.state.job(job['id'])['status']=='requires_browser'
    file=workspace/'downloaded.glb';file.write_bytes(assets['model.glb'])
    result=router.complete_browser(job['id'],[str(file)],'https://studio.tripo3d.ai/task/123')
    assert result['status']=='completed'
    assert result['data']['provenance']['attestation']=='reported_by_host_not_provider_verified'


def test_browser_receipt_does_not_trust_wrong_origin(router,workspace,assets):
    j=router.run('tripo.web',{'task':'x'},workspace)
    p=workspace/'file.glb';p.write_bytes(assets['model.glb'])
    with pytest.raises(RouterError): router.complete_browser(j['id'],[str(p)],'https://evil.example/result')


def test_browser_output_type_must_match(router,workspace,assets):
    j=router.run('tripo.web',{'task':'x'},workspace)
    p=workspace/'not-a-model.png';p.write_bytes(assets['image.png'])
    with pytest.raises(RouterError): router.complete_browser(j['id'],[str(p)],'https://studio.tripo3d.ai/task/1')


def test_browser_block_and_resume(router,workspace):
    j=router.run('suno.web',{'task':'music'},workspace)
    assert router.block_browser(j['id'],'login_required')['status']=='login_required'
    assert router.block_browser(j['id'],'requires_browser')['status']=='requires_browser'


def test_api_job_cannot_be_forged_completed(router,workspace):
    j=router.run('tripo.text_to_3d',{'prompt':'x'},workspace,allow_paid=True)
    with pytest.raises(RouterError): router.complete_browser(j['id'],[],'https://studio.tripo3d.ai/')


def test_youtube_is_reference_manifest(router,workspace):
    j=router.run('youtube.web',{'task':'Find a video reference'},workspace)
    assert 'not a general YouTube downloader' in j['data']['handoff']['steps'][-1]
    assert j['data']['handoff']['accepted_extensions']==['.json']
