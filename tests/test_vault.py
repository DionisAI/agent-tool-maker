import base64
import os
import pytest
from agent_tool_maker.errors import RouterError
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault


def test_ciphertext_at_rest_and_reopen(tmp_path):
    s=State(tmp_path/'vault');v=Vault(s,password='a-long-enough-password');v.init('passphrase')
    secret='actual-test-secret-never-persist-plaintext'
    v.put('fal',secret)
    assert secret.encode() not in s.path.read_bytes()
    assert Vault(s,password='a-long-enough-password').get('fal')==secret
    assert not list(s.home.glob('*key*'))


def test_wrong_password(tmp_path):
    s=State(tmp_path/'v');v=Vault(s,password='correct-passphrase');v.init('passphrase');v.put('fal','secret')
    with pytest.raises(RouterError,match='Incorrect'): Vault(s,password='wrong-passphrase').get('fal')


def test_tampering_detected(router):
    with router.state.db() as c:
        c.execute("UPDATE secrets SET ciphertext=? WHERE name='fal'",(b'corrupted ciphertext',))
    with pytest.raises(RouterError,match='authentication failed'): router.vault.get('fal')


def test_secret_bound_to_provider_name(router):
    with router.state.db() as c:
        row=c.execute("SELECT nonce,ciphertext FROM secrets WHERE name='fal'").fetchone()
        c.execute("UPDATE secrets SET nonce=?,ciphertext=? WHERE name='tripo'",tuple(row))
    with pytest.raises(RouterError): router.vault.get('tripo')


@pytest.mark.parametrize('value',['','a\nb','a\rb','a\x00b','x'*16385])
def test_bad_values(router,value):
    with pytest.raises(RouterError): router.vault.put('fal',value)


def test_repeat_init_does_not_destroy(router):
    before=router.vault.get('fal')
    with pytest.raises(RouterError): router.vault.init('passphrase')
    assert router.vault.get('fal')==before


def test_redaction(router):
    key=router.vault.get('fal')
    assert key not in str(router.vault.redact({'x':'prefix '+key,'Authorization':'abc'}))


def test_remove(router):
    router.vault.delete('fal')
    assert 'fal' not in router.state.secret_names()
    with pytest.raises(RouterError): router.vault.get('fal')


def test_keyring_mode_with_contract_double(tmp_path):
    class Keyring:
        def __init__(self): self.values={}
        def set_password(self,s,a,v): self.values[s,a]=v
        def get_password(self,s,a): return self.values.get((s,a))
    backend=Keyring();s=State(tmp_path/'v')
    v=Vault(s,keyring_backend=backend);v.init('keyring');v.put('fal','keyring-test-value')
    assert Vault(s,keyring_backend=backend).get('fal')=='keyring-test-value'
    assert list(backend.values.values())[0].encode() not in s.path.read_bytes()


def test_native_keyring_failure_is_explicit(tmp_path):
    class Broken:
        def set_password(self,*args): raise RuntimeError('do not echo secret')
    with pytest.raises(RouterError,match='write failed'):
        Vault(State(tmp_path/'v'),keyring_backend=Broken()).init('keyring')


def test_permission_modes(router):
    if os.name=='posix':
        assert router.state.path.stat().st_mode&0o777==0o600
        assert router.state.home.stat().st_mode&0o777==0o700
