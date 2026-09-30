import copy
import itertools
import json
from pathlib import Path

import pytest
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.vault import Vault
from agent_tool_maker.sync import Sync, merge, strict_json, write_sync_file, read_sync_file
from agent_tool_maker.errors import RouterError


@pytest.fixture
def nodes(tmp_path):
    result=[]
    for label in ['laptop','server','desktop']:
        v=Vault(State(tmp_path/label),password='test-only-long-passphrase')
        v.init('passphrase')
        s=Sync(v);s.initialize(label);result.append(s)
    return result


def pair(a,b,providers=('fal','elevenlabs'), *, receive=None):
    for x,y in [(a,b),(b,a)]:
        x.trust(y.identity(),y.identity()['id'],send=list(providers),receive=list(providers if receive is None else receive),apply=True)


def send(a,b,**kw):
    return b.import_packet(a.export_packet(b.identity()['id']),apply=True,**kw)


def versions(s,name='fal'):
    from agent_tool_maker.sync import _load
    with s.state.db() as db:return _load(db,s.vault.unlock(),name)


def test_first_copy_uses_distinct_local_encryption(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-only-at-owner')
    packet=a.export_packet(b.identity()['id'])
    assert 'FAKE-only-at-owner' not in canonical(packet)
    assert 'fal' not in canonical(packet)  # provider names are inside encrypted payload
    before=b.state.path.read_bytes()
    preview=b.import_packet(packet)
    assert preview['changes'][0]['changed'] and not b.state.secret_names()
    b.import_packet(packet,apply=True)
    assert b.vault.get('fal')=='FAKE-only-at-owner'
    assert a.vault.unlock()!=b.vault.unlock()
    assert 'FAKE-only-at-owner'.encode() not in b.state.path.read_bytes()
    assert 'FAKE-only-at-owner' not in canonical(b.status())


def test_different_providers_merge(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-a');b.vault.put('elevenlabs','FAKE-b')
    send(a,b);send(b,a)
    assert a.vault.get('elevenlabs')==b.vault.get('elevenlabs')=='FAKE-b'
    assert a.vault.get('fal')==b.vault.get('fal')=='FAKE-a'


def test_offline_conflict_blocks_then_explicit_resolution(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-base');send(a,b)
    a.vault.put('fal','FAKE-left');b.vault.put('fal','FAKE-right')
    send(a,b);send(b,a)
    for s in (a,b):
        assert s.status()['conflicts']==1
        with pytest.raises(RouterError,match='concurrent|Concurrent'):s.vault.get('fal')
        with pytest.raises(RouterError) as e:s.vault.put('fal','FAKE-silent-overwrite')
        assert e.value.code=='sync_conflict'
    heads=a.status()['records'][0]
    chosen=next(v for v in versions(a) if v['value']=='FAKE-left')['revision']
    a.resolve('fal',chosen,heads['expected'])
    assert a.status()['conflicts']==1
    a.resolve('fal',chosen,heads['expected'],apply=True)
    send(a,b)
    assert b.vault.get('fal')=='FAKE-left' and b.status()['conflicts']==0


def test_replay_cannot_revert_newer_key(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-old');old=a.export_packet(b.identity()['id']);b.import_packet(old,apply=True)
    a.vault.put('fal','FAKE-new');send(a,b)
    before=b.state.setting('credential_meta:fal')
    again=b.import_packet(old,apply=True)
    assert not again['changes'][0]['changed']
    assert b.vault.get('fal')=='FAKE-new' and b.state.setting('credential_meta:fal')==before


def test_delete_tombstone_does_not_resurrect(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-old');old=a.export_packet(b.identity()['id']);send(a,b)
    a.vault.delete('fal');send(a,b);b.import_packet(old,apply=True)
    assert not b.state.secret_names() and b.status()['records'][0]['state']=='deleted'


def test_delete_vs_update_is_conflict(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-base');send(a,b)
    a.vault.delete('fal');b.vault.put('fal','FAKE-new');send(a,b)
    assert b.status()['conflicts']==1
    row=b.status()['records'][0];deleted=next(h for h in row['heads'] if h['deleted'])
    b.resolve('fal',deleted['revision'],row['expected'],apply=True);send(b,a)
    assert not a.state.secret_names() and not b.state.secret_names()


def test_identical_value_concurrent_writes_converge_without_prompt(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-same');b.vault.put('fal','FAKE-same');send(a,b);send(b,a)
    assert not a.status()['conflicts'] and len(versions(a))==2
    assert a.vault.get('fal')=='FAKE-same'


def test_expiry_is_atomic_with_key_not_field_merged(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-same',expires_at=2000000000)
    b.vault.put('fal','FAKE-same',expires_at=2000000001)
    send(a,b);assert b.status()['conflicts']==1


def test_stale_resolution_refused(nodes):
    a,b,c=nodes
    for x,y in itertools.combinations(nodes,2):pair(x,y)
    a.vault.put('fal','FAKE-a');b.vault.put('fal','FAKE-b');send(a,b)
    reviewed=b.status()['records'][0]
    c.vault.put('fal','FAKE-c');send(c,b)
    with pytest.raises(RouterError) as e:b.resolve('fal',reviewed['heads'][0]['revision'],reviewed['expected'],apply=True)
    assert e.value.code=='conflict_changed' and b.status()['conflicts']==1


def test_concurrent_resolutions_make_a_new_conflict(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-a');b.vault.put('fal','FAKE-b');send(a,b);send(b,a)
    row=a.status()['records'][0]
    a.resolve('fal',row['heads'][0]['revision'],row['expected'],apply=True)
    b.resolve('fal',row['heads'][1]['revision'],row['expected'],apply=True)
    send(a,b);assert b.status()['conflicts']==1


def test_three_node_register_join_properties(nodes):
    for i,n in enumerate(nodes):n.vault.put('fal','FAKE-'+str(i))
    a,b,c=[versions(n) for n in nodes]
    expected=merge(merge(a,b),c)
    for items in itertools.permutations([a,b,c]):assert merge(merge(items[0],items[1]),items[2])==expected
    assert merge(expected,expected)==expected
    assert merge(a,merge(b,c))==expected


@pytest.mark.parametrize('field',['ciphertext','signature','sender','recipient','nonce','salt','ephemeral','packet','format'])
def test_envelope_tampering_is_rejected_atomically(nodes,field):
    a,b,c=nodes;pair(a,b);a.vault.put('fal','FAKE-sensitive')
    packet=a.export_packet(b.identity()['id'])
    if field in packet:
        v=packet[field];packet[field]=('A' if v[0]!='A' else 'B')+v[1:]
    else:packet['header'][field]='bad-value'
    with pytest.raises(RouterError):b.import_packet(packet,apply=True)
    assert b.state.secret_names()==[]


def test_unknown_peer_and_bad_fingerprint(nodes):
    a,b,c=nodes
    with pytest.raises(RouterError):a.trust(b.identity(),'0'*64,send=['fal'],apply=True)
    pair(a,b);a.vault.put('fal','FAKE-a')
    with pytest.raises(RouterError):c.import_packet(a.export_packet(b.identity()['id']),apply=True)


def test_scope_denies_entire_packet_not_partial(nodes):
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-f');a.vault.put('elevenlabs','FAKE-e')
    b.trust(a.identity(),a.identity()['id'],receive=['fal'],send=[],apply=True,replace=True)
    with pytest.raises(RouterError) as e:send(a,b)
    assert e.value.code=='sync_scope_denied' and not b.state.secret_names()


def test_send_scope_minimizes_server_copy(nodes):
    a,b,_=nodes;pair(a,b,['fal'])
    a.vault.put('fal','FAKE-f');a.vault.put('elevenlabs','FAKE-e');send(a,b)
    assert b.state.secret_names()==['fal']


def test_revoked_peer_cannot_import_or_receive(nodes):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-f')
    packet=a.export_packet(b.identity()['id']);b.revoke(a.identity()['id'],apply=True)
    with pytest.raises(RouterError):b.import_packet(packet,apply=True)
    with pytest.raises(RouterError):b.export_packet(a.identity()['id'])


def test_initialization_migrates_existing_key_and_never_reinitializes(tmp_path):
    v=Vault(State(tmp_path/'v'),password='this-is-only-a-test-password');v.init('passphrase');v.put('fal','FAKE-before')
    s=Sync(v);original=v.unlock();card=s.initialize('one')['device']
    assert s.initialize('another')['device']==card and v.unlock()==original
    assert versions(s)[0]['value']=='FAKE-before'


def test_exchange_shared_folder_and_no_redundant_push(nodes,tmp_path):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-a')
    folder=tmp_path/'encrypted'
    preview=a.exchange(folder);assert not folder.exists() and preview['outgoing']
    a.exchange(folder,apply=True);b.exchange(folder,apply=True);a.exchange(folder,apply=True)
    assert b.vault.get('fal')=='FAKE-a'
    assert not a.exchange(folder,apply=True)['outgoing']
    a.vault.put('fal','FAKE-rotated');a.exchange(folder,apply=True);b.exchange(folder,apply=True)
    assert b.vault.get('fal')=='FAKE-rotated'
    assert all(b'FAKE-' not in p.read_bytes() for p in folder.rglob('*.atmsync'))


def test_local_paths_private_identity_and_permissions_never_sync(nodes):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-f')
    a.state.set_setting('origin:evil','https://not-allowed.example')
    a.state.set_setting('cli:wrangler','/some/machine/path')
    a.state.set_setting('access:fake',{'scope':'all'})
    send(a,b)
    assert b.state.setting('origin:evil') is None and b.state.setting('cli:wrangler') is None
    assert b.state.setting('access:fake') is None and a.identity()['id']!=b.identity()['id']


def test_duplicate_json_and_file_symlinks_rejected(tmp_path):
    with pytest.raises(RouterError):strict_json('{"a":1,"a":2}')
    f=tmp_path/'out';write_sync_file(f,b'abc')
    with pytest.raises(RouterError):write_sync_file(f,b'def')
    link=tmp_path/'link';link.symlink_to(f)
    with pytest.raises(RouterError):read_sync_file(link)
    assert f.read_bytes()==b'abc' and f.stat().st_mode&0o077==0


def test_cross_process_conflict_health(nodes):
    from agent_tool_maker.engine import Router
    from agent_tool_maker.health import doctor
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-a');b.vault.put('fal','FAKE-b');send(a,b)
    r=Router(b.state.home)
    try:
        assert r.readiness(r.catalog.get('fal.generate'))=='sync_conflict'
        assert doctor(r,tool_ids=['fal.generate'])['tools'][0]['state']=='sync_conflict'
    finally:r.close()


def test_old_client_mutation_detected_not_exported(nodes):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-original')
    nonce=os.urandom(12)
    with a.state.db() as db:db.execute('UPDATE secrets SET nonce=?,ciphertext=? WHERE name=?',(nonce,AESGCM(a.vault.unlock()).encrypt(nonce,b'FAKE-old-client-write',b'fal'),'fal'))
    with pytest.raises(RouterError) as e:a.export_packet(b.identity()['id'])
    assert e.value.code=='sync_state_drift'


def test_multiple_local_writes_have_distinct_causal_revisions(nodes):
    from concurrent.futures import ThreadPoolExecutor
    a,_,_=nodes
    def put(i):
        v=Vault(a.state);v._key=a.vault.unlock();v.put('fal','FAKE-'+str(i))
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(put,range(16)))
    current=versions(a)
    assert len(current)==1 and current[0]['clock'][a.identity()['id']]==16


def test_concurrent_imports_do_not_lose_a_sibling(nodes):
    from concurrent.futures import ThreadPoolExecutor
    a,b,c=nodes;pair(a,c);pair(b,c);a.vault.put('fal','FAKE-a');b.vault.put('fal','FAKE-b')
    packets=[a.export_packet(c.identity()['id']),b.export_packet(c.identity()['id'])]
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda p:c.import_packet(p,apply=True),packets))
    assert c.status()['conflicts']==1 and len(versions(c))==2


def test_exchange_scope_change_and_deleted_transport_file_republish(nodes,tmp_path):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-a');folder=tmp_path/'sync';first=a.exchange(folder,apply=True)
    Path(first['outgoing'][0]['file']).unlink()
    second=a.exchange(folder,apply=True);assert second['outgoing']
    a.trust(b.identity(),b.identity()['id'],send=['fal'],receive=[],replace=True,apply=True)
    assert a.exchange(folder,apply=True)['outgoing']


def test_revocation_cannot_recover_already_sent_secrets(nodes):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-already-delivered');send(a,b)
    a.revoke(b.identity()['id'],apply=True)
    assert b.vault.get('fal')=='FAKE-already-delivered'  # explicitly tested limitation


def test_wrong_vault_passphrase_cannot_read_packet(nodes):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-a')
    wrong=Sync(Vault(b.state,password='definitely-wrong-passphrase'))
    with pytest.raises(RouterError):wrong.import_packet(a.export_packet(b.identity()['id']),apply=True)
    assert not b.state.secret_names()


def test_authorized_malformed_snapshot_rejected_before_any_write(nodes,monkeypatch):
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-a');a.vault.put('elevenlabs','FAKE-e')
    snapshot=a._snapshot(b.identity()['id'])
    snapshot['records']['elevenlabs'][0]['clock']={a.identity()['id']:True}
    monkeypatch.setattr(a,'_snapshot',lambda _:snapshot)
    with pytest.raises(RouterError):send(a,b)
    assert not b.state.secret_names()


def test_watch_lease_has_no_hidden_infinite_run(nodes,tmp_path):
    from agent_tool_maker.sync import watch
    a,b,_=nodes;pair(a,b);a.vault.put('fal','FAKE-a')
    report=watch(a.vault,tmp_path/'sync',interval=5,ttl_hours=0.0001)
    assert report['cycles']==1 and a.vault._key is None


def test_resolution_rejects_old_client_drift(nodes):
    import os
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    a,b,_=nodes;pair(a,b)
    a.vault.put('fal','FAKE-A');b.vault.put('fal','FAKE-B');send(a,b)
    row=b.status()['records'][0]
    nonce=os.urandom(12);cipher=AESGCM(b.vault.unlock()).encrypt(nonce,b'FAKE-untracked','fal'.encode())
    with b.state.db() as db:db.execute('INSERT INTO secrets VALUES (?,?,?)',('fal',nonce,cipher))
    with pytest.raises(RouterError) as e:b.resolve('fal',row['heads'][0]['revision'],row['expected'],apply=True)
    assert e.value.code=='sync_state_drift'
