"""Real Unix-socket transport failures; synthetic profiles and no supplier calls."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import tempfile
import threading

import pytest

from agent_tool_maker.broker import call
from agent_tool_maker.errors import RouterError


pytestmark = pytest.mark.integration


@pytest.fixture
def socket_reply():
    @contextmanager
    def serve(response):
        # Keep AF_UNIX paths short and canonical, including on macOS.
        with tempfile.TemporaryDirectory(prefix='atm-eof-') as directory:
            root = Path(directory).resolve()
            socket_path = root / 's'
            profile = root / 'client.json'
            profile.write_text(json.dumps({
                'format': 'atm-client-v1', 'id': 'fixture-client', 'agent': 'codex',
                'socket': str(socket_path), 'token': 'fake-transport-token',
                'socket_owner_uid': os.getuid(), 'socket_gid': None,
            }))
            profile.chmod(0o600)
            received, failures = [], []
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(socket_path))
                socket_path.chmod(0o600)
                listener.listen(1)
                listener.settimeout(5)

                def respond_once():
                    try:
                        connection, _ = listener.accept()
                        with connection:
                            connection.settimeout(5)
                            with connection.makefile('rb') as stream:
                                received.append(json.loads(stream.readline()))
                            if response:
                                connection.sendall(response)
                    except Exception as error:
                        failures.append(error)

                thread = threading.Thread(target=respond_once, daemon=True)
                thread.start()
                try:
                    yield profile, received
                finally:
                    thread.join(6)
                    assert not thread.is_alive(), 'Socket fixture did not finish'
                    assert not failures, failures

    return serve


@pytest.mark.parametrize('operation,uncertain', [
    ('status', False), ('session.status', False), ('exec', True), ('run', True),
])
def test_eof_is_unavailable_and_preserves_submission_uncertainty(socket_reply, operation, uncertain):
    with socket_reply(b'') as (profile, received):
        with pytest.raises(RouterError) as error:
            call(profile, operation, {'request_key': 'stable-fixture-request'}, timeout=3)
        assert error.value.code == 'broker_unavailable'
        assert error.value.uncertain is uncertain
        assert error.value.as_dict()['outcome_uncertain'] is uncertain
        assert len(received) == 1  # No automatic retry after a lost response.
        assert received[0]['operation'] == operation
        assert received[0]['args']['request_key'] == 'stable-fixture-request'
        assert 'fake-transport-token' not in str(error.value)


@pytest.mark.parametrize('response', [b'\n', b'not-json\n', b'{"result":'])
def test_nonempty_malformed_reply_remains_a_protocol_error(socket_reply, response):
    with socket_reply(response) as (profile, received):
        with pytest.raises(RouterError) as error:
            call(profile, 'status', {}, timeout=3)
        assert error.value.code == 'invalid_sync'
        assert error.value.uncertain is False
        assert len(received) == 1


def test_duplicate_reply_keys_remain_rejected(socket_reply):
    with socket_reply(b'{"result":{},"result":{}}\n') as (profile, received):
        with pytest.raises(RouterError) as error:
            call(profile, 'status', {}, timeout=3)
        assert error.value.code == 'duplicate_json_key'
        assert len(received) == 1


@pytest.mark.parametrize('uncertain', [False, True])
def test_structured_remote_errors_keep_their_code_and_uncertainty(socket_reply, uncertain):
    response = json.dumps({'error': {
        'code': 'broker_locked', 'message': 'fixture locked', 'outcome_uncertain': uncertain,
    }}).encode() + b'\n'
    with socket_reply(response) as (profile, received):
        with pytest.raises(RouterError) as error:
            call(profile, 'exec', {}, timeout=3)
        assert error.value.code == 'broker_locked'
        assert error.value.uncertain is uncertain
        assert str(error.value) == 'fixture locked'
        assert len(received) == 1


def test_valid_reply_still_returns_its_result(socket_reply):
    with socket_reply(b'{"result":{"status":"fixture-ready"}}\n') as (profile, received):
        assert call(profile, 'status', {}, timeout=3) == {'status': 'fixture-ready'}
        assert len(received) == 1
