"""atm inventory: what ATM holds and how an Agent uses it, never a value; works while locked."""
import json
import subprocess
import sys

import pytest

from agent_tool_maker.extensions import declare_credential
from agent_tool_maker.inventory import inventory
from agent_tool_maker.secrets_provider import alias
from agent_tool_maker.vault import Vault


def test_inventory_lists_keys_slots_services_and_how_to_without_values(router, monkeypatch):
    declare_credential(router, 'wisburg', label='智堡 Wisburg', apply=True)
    alias(router.state, 'WISBURG_API_KEY', ['wisburg'], apply=True)
    alias(router.state, 'FAL_KEY', ['fal'], apply=True)
    # The vault is never opened: the listing must work while ATM is locked.
    monkeypatch.setattr(Vault, 'unlock', lambda self: pytest.fail('inventory must not open the vault'))
    monkeypatch.setattr(Vault, 'get', lambda self, name: pytest.fail('inventory must not read a Key'))
    result = inventory(router)
    keys = {k['name']: k for k in result['keys']}
    assert {'elevenlabs', 'fal', 'exa'} <= set(keys)
    assert keys['fal']['reference'] == 'atm://fal' and keys['fal']['env_names'] == ['FAL_KEY']
    assert result['declared_without_key'] == [{'name': 'wisburg', 'label': '智堡 Wisburg', 'reference': 'atm://wisburg',
                                               'env_names': ['WISBURG_API_KEY'], 'state': 'missing_credential', 'expires_at': None}]
    providers = {s['provider']: s for s in result['services']}
    assert 'elevenlabs' in providers and providers['elevenlabs']['ready_tools'] >= 1
    assert result['session']['unlocked'] is False and result['oauth'][0]['provider'] == 'higgsfield'
    assert result['mcp_servers'] == [] and result['web_logins'] == []
    assert 'atm use' in result['how_to']['use_key'] and '1Password' in result['how_to']['unlock']
    assert result['secrets_returned'] is False and result['network_calls'] == 0
    assert 'FAKE_' not in json.dumps(result, ensure_ascii=False)


def test_inventory_shows_owner_added_mcp_servers(router):
    from agent_tool_maker import mcp_servers
    declare_credential(router, 'wisburg', apply=True)
    preview = mcp_servers.add(router, 'wisburg', 'https://mcp.example.com/mcp', 'wisburg', allow_tools=['read'])
    mcp_servers.add(router, 'wisburg', 'https://mcp.example.com/mcp', 'wisburg', allow_tools=['read'], approve=preview['plan_sha256'])
    servers = inventory(router)['mcp_servers']
    assert [(s['server'], s['endpoint'], s['credential'], s['allow_tools']) for s in servers] == [
        ('wisburg', 'https://mcp.example.com/mcp', 'wisburg', ['read'])]


def test_cli_inventory_is_one_json_document(tmp_path):
    home = tmp_path / 'home'
    run = lambda *a: subprocess.run([sys.executable, '-m', 'agent_tool_maker', '--home', str(home), *a],
                                    capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert run('credentials', 'declare', 'wisburg', '--apply').returncode == 0
    p = run('inventory')
    data = json.loads(p.stdout)
    assert p.returncode == 0 and data['declared_without_key'][0]['name'] == 'wisburg' and data['secrets_returned'] is False
