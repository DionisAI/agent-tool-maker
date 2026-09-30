from pathlib import Path
import httpx
import pytest
from agent_tool_maker.demo import FixtureProvider,fixture_assets,fixture_resolver
from agent_tool_maker.engine import Router
from agent_tool_maker.network import Network
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault

@pytest.fixture
def assets(): return fixture_assets()

@pytest.fixture
def fixture_provider(): return FixtureProvider()

@pytest.fixture
def router(tmp_path,fixture_provider):
    state=State(tmp_path/'state')
    vault=Vault(state,password='unit-test-passphrase-long')
    vault.init('passphrase')
    for name in ['elevenlabs','fal','higgsfield','tripo','exa','firecrawl']:
        vault.put(name,'FAKE_'+name+(':FAKE_SECRET' if name=='higgsfield' else ''))
    r=Router(state.home,network=Network(httpx.MockTransport(fixture_provider),fixture_resolver),vault=vault)
    yield r
    r.close()

@pytest.fixture
def workspace(tmp_path):
    p=tmp_path/'workspace';p.mkdir()
    return p
