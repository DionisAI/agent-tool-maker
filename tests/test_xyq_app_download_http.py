"""Actual loopback HTTP fixture; no browser, accounts or provider requests."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import hashlib
import json
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
from urllib.parse import urlsplit
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_loopback_fixture_idle_preconnection_and_concurrent_one_download(tmp_path):
    output = tmp_path / "probe"
    process = subprocess.Popen([sys.executable, str(ROOT / 'tests/fixtures/xyq_app_download_http.py'),
                                '--output', str(output)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)
    idle = None
    try:
        assert select.select([process.stdout], [], [], 10)[0], 'No fixture startup receipt'
        line = process.stdout.readline()
        assert line, process.stderr.read()
        initial = json.loads(line)
        url = urlsplit(initial['origin'])
        assert url.hostname == '127.0.0.1' and initial['provider_called'] is False
        # This idle Chrome-style preconnection used to stall a single-threaded
        # HTTPServer. Status/file requests should remain available beside it.
        idle = socket.create_connection((url.hostname, url.port), timeout=2)

        def get(path):
            connection = HTTPConnection(url.hostname, url.port, timeout=3)
            try:
                connection.request('GET', path)
                response = connection.getresponse()
                return response.status, response.getheader('Content-Type'), response.read()
            finally:
                connection.close()

        code, mime, body = get('/status')
        assert code == 200 and mime == 'application/json' and json.loads(body)['download_requests'] == 0
        code, mime, body = get('/')
        assert code == 200 and mime == 'text/html; charset=utf-8' and initial['filename'].encode() in body
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(get, ['/' + initial['filename']] * 2))
        assert sorted(result[0] for result in results) == [200, 409]
        success = next(result for result in results if result[0] == 200)
        assert success[1] == 'image/png' and hashlib.sha256(success[2]).hexdigest() == initial['image_sha256']
        assert json.loads(get('/status')[2])['download_requests'] == 2
        assert get('/unknown')[0] == 404
    finally:
        if idle:
            idle.close()
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        process.wait(timeout=10)
    assert process.returncode == 0
    final = json.loads((output / 'server-final.json').read_text())
    assert final['status'] == 'fixture_server_stopped' and final['download_requests'] == 2 and final['provider_called'] is False
