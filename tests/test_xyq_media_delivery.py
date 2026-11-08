"""Decoded synthetic media and real source-ATM subprocesses; no provider activity."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import wave
import zlib

from PIL import Image, PngImagePlugin
import pytest
from agent_tool_maker import media as m
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.extensions import pack, validate_bundle
from agent_tool_maker.maker import digest, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('xyq_media_builder', ROOT/'scripts/build_xyq_media.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def image(workspace, name='test.png'):
    path = workspace/name; path.parent.mkdir(parents=True, exist_ok=True)
    info = PngImagePlugin.PngInfo(); info.add_text('comment', 'FAKE_PRIVATE_PROMPT_AND_TAG')
    Image.new('RGB', (32, 16), 'blue').save(path, pnginfo=info if path.suffix == '.png' else None)
    return path


def wav(workspace, name='test.wav'):
    path = workspace/name
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 16000)
    return path


@pytest.fixture(scope='session')
def tools():
    return b.toolchain()


@pytest.fixture
def av_files(workspace, tools):
    executable = tools['ffmpeg']['path']; mp3 = workspace/'test.mp3'; mp4 = workspace/'test.mp4'
    subprocess.run([executable, '-nostdin', '-v', 'error', '-n', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=16000:duration=0.5', '-c:a', 'libmp3lame',
                    '-metadata', 'comment=FAKE_PRIVATE_TAG', str(mp3)], check=True, capture_output=True)
    subprocess.run([executable, '-nostdin', '-v', 'error', '-n', '-f', 'lavfi', '-i',
                    'color=c=blue:s=64x64:r=8:d=0.5', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=16000:duration=0.5', '-t', '0.5',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart',
                    '-metadata', 'comment=FAKE_PRIVATE_TAG', str(mp4)], check=True, capture_output=True)
    return {'mp3': mp3, 'mp4': mp4}


def inspect(workspace, path, kind, tools=None, expected=None):
    return m.inspect_media(workspace, str(path.relative_to(workspace)), kind, expected or sha(path), tools)


def test_manifest_is_fixed_local_unpaid_and_separate_from_web_definitions(tools):
    tool = b.manifest(tools)
    assert tool['id'] == 'xyq.media.artifact_inspect' and tool['executable'] == 'atm'
    assert tool['permissions'] == ['execute_code'] and not tool['paid'] and 'credential' not in tool
    assert tool['schema']['required'] == ['file', 'kind', 'expected_sha256']
    assert tool['schema']['additionalProperties'] is False
    assert tool['command']['argv'][:2] == ['media', 'adapter']
    assert m.source_digest() in tool['command']['argv']
    for item in tools.values():
        assert item['path'] in tool['command']['argv'] and item['sha256'] in tool['command']['argv']


@pytest.mark.parametrize('name,fmt', [('test.png', 'png'), ('test.jpg', 'jpeg'), ('test.webp', 'webp')])
def test_complete_images_are_decoded_with_whitelisted_metadata(workspace, name, fmt):
    path = image(workspace, name); before = path.read_bytes(); result = inspect(workspace, path, 'image')
    assert result['status'] == 'artifact_verified' and result['valid'] and result['format'] == fmt
    assert result['sha256'] == sha(path) and result['bytes'] == len(before) and path.read_bytes() == before
    assert result['media']['width'] == 32 and result['media']['height'] == 16
    assert result['complete_decode_verified'] and result['network_calls'] == 0 and not result['credentials_read']
    for key in ['download_verified', 'task_association_verified', 'provider_generation_verified', 'paid_submitted', 'upload_started', 'generation_submitted']:
        assert result[key] is False
    assert 'FAKE_PRIVATE' not in json.dumps(result) and 'comment' not in result['media']


def test_complete_pcm_wav_checks_every_frame_without_decoder_tools(workspace):
    path = wav(workspace); result = inspect(workspace, path, 'audio')
    assert result['media'] == {'sample_rate_hz': 16000, 'channels': 1, 'sample_width_bytes': 2,
                              'frame_count': 16000, 'duration_seconds': 1.0, 'duration_source': 'pcm_frames'}
    assert result['complete_decode_verified'] and 'decoder_sha256' not in result['media']


@pytest.mark.integration
@pytest.mark.parametrize('fmt,kind', [('mp3', 'audio'), ('mp4', 'video')])
def test_real_pinned_ffprobe_and_full_ffmpeg_decode(workspace, tools, av_files, fmt, kind, monkeypatch):
    calls = []; original = m._run
    def spy(executable, argv, fd, phase):
        calls.append(argv)
        assert argv[argv.index('-protocol_whitelist')+1] == 'fd'
        assert argv[argv.index('-i')+1] == 'fd:' and argv[argv.index('-fd')+1] == str(fd)
        assert str(av_files[fmt]) not in argv
        if fmt == 'mp4':
            assert argv[argv.index('-enable_drefs')+1] == '0' and argv[argv.index('-use_absolute_path')+1] == '0'
        return original(executable, argv, fd, phase)
    monkeypatch.setattr(m, '_run', spy)
    path = av_files[fmt]; before = path.read_bytes(); result = inspect(workspace, path, kind, tools)
    assert result['status'] == 'artifact_verified' and result['complete_decode_verified']
    assert result['media']['duration_seconds'] > 0 and result['media']['duration_source'] == 'container_metadata'
    assert 0 < result['media']['decoded_output_time_seconds'] <= m.MAX_SECONDS
    assert result['media']['decoder_sha256'] == {k: v['sha256'] for k, v in tools.items()}
    assert path.read_bytes() == before and 'FAKE_PRIVATE' not in json.dumps(result)
    assert len(calls) == 2
    assert all(set(s) <= {'type', 'codec', 'width', 'height', 'sample_rate_hz', 'channels'} for s in result['media']['streams'])
    if fmt == 'mp4':
        assert result['media']['decoded_frame_count'] == 4
    else:
        assert result['media']['container_frame_count'] > 0


@pytest.mark.parametrize('file,code', [('../test.png', 'media_path_invalid'), ('/test.png', 'media_path_invalid'),
    ('sub//test.png', 'media_path_invalid'), ('sub/./test.png', 'media_path_invalid'),
    ('https://example.test/test.png', 'media_path_invalid'), ('test.html', 'media_unsupported')])
def test_outside_or_unknown_paths_stop_before_file_reads(workspace, file, code):
    with pytest.raises(m.MediaError) as error:
        m.inspect_media(workspace, file, 'image', '0'*64)
    assert error.value.code == code and error.value.phase == 'file_eligibility'


@pytest.mark.parametrize('kind,expected', [(None, '0'*64), ({}, '0'*64), ('image', None), ('image', 1), ('image', 'F'*64)])
def test_invalid_media_arguments_are_typed_without_reading_files(workspace, kind, expected):
    with pytest.raises(m.MediaError) as error:
        m.inspect_media(workspace, 'test.png', kind, expected)
    assert error.value.code == 'invalid_argument' and error.value.phase == 'arguments'


@pytest.mark.parametrize('value,code', [(True, 'media_unsupported'), (None, 'media_unsupported'),
    ({}, 'media_unsupported'), ('NaN', 'media_limit'), ('Infinity', 'media_limit'), ('0', 'media_limit'), ('-1', 'media_limit')])
def test_duration_observations_are_finite_positive_numbers(value, code):
    with pytest.raises(m.MediaError) as error: m._number(value, 'media_probe')
    assert error.value.code == code and error.value.phase == 'media_probe'


@pytest.mark.parametrize('variant', ['leaf', 'parent', 'workspace', 'hardlink', 'fifo'])
def test_linked_or_special_media_paths_stop_before_decode(workspace, tmp_path, variant):
    path = image(workspace); selected = 'test.png'; root = workspace
    if variant == 'leaf':
        (workspace/'alias.png').symlink_to(path); selected = 'alias.png'
    elif variant == 'parent':
        (workspace/'alias').symlink_to(workspace, target_is_directory=True); selected = 'alias/test.png'
    elif variant == 'workspace':
        root = tmp_path/'workspace-alias'; root.symlink_to(workspace, target_is_directory=True)
    elif variant == 'hardlink':
        os.link(path, workspace/'alias.png'); selected = 'alias.png'
    else:
        os.mkfifo(workspace/'pipe.png'); selected = 'pipe.png'
    with pytest.raises(m.MediaError) as error:
        m.inspect_media(root, selected, 'image', sha(path))
    assert error.value.code == 'media_path_invalid'


def test_hash_mismatch_is_checked_before_image_decoder(workspace, monkeypatch):
    path = image(workspace)
    monkeypatch.setattr(m, '_image', lambda *a: pytest.fail('Decode after wrong SHA'))
    with pytest.raises(m.MediaError) as error:
        inspect(workspace, path, 'image', expected='0'*64)
    assert error.value.code == 'media_hash_mismatch'


@pytest.mark.parametrize('variant,code', [('empty', 'media_size_limit'), ('html', 'media_format_mismatch'),
    ('header', 'media_incomplete'), ('truncated', 'media_incomplete'), ('extension', 'media_format_mismatch')])
def test_image_error_pages_and_incomplete_bytes_never_validate(workspace, variant, code):
    path = image(workspace)
    if variant == 'empty': path.write_bytes(b'')
    elif variant == 'html': path.write_bytes(b'<html>FAKE_PRIVATE_LOGIN_REQUIRED</html>')
    elif variant == 'header': path.write_bytes(b'\x89PNG\r\n\x1a\n')
    elif variant == 'truncated': path.write_bytes(path.read_bytes()[:-1])
    else:
        other = workspace/'test.jpg'; other.write_bytes(path.read_bytes()); path = other
    with pytest.raises(m.MediaError) as error:
        inspect(workspace, path, 'image')
    assert error.value.code == code and 'FAKE_PRIVATE' not in json.dumps(error.value.as_dict())


def test_pixel_limit_and_animation_do_not_become_header_only_success(workspace, monkeypatch):
    path = image(workspace)
    monkeypatch.setattr(m, 'MAX_PIXELS', 10)
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'image')
    assert error.value.code == 'media_limit'
    monkeypatch.setattr(m, 'MAX_PIXELS', 40_000_000)
    path = workspace/'animated.webp'
    Image.new('RGB', (16, 16), 'blue').save(path, save_all=True, append_images=[Image.new('RGB', (16, 16), 'red')], duration=100)
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'image')
    assert error.value.code == 'media_unsupported'


def test_png_valid_crc_and_header_still_require_real_pixel_decode(workspace):
    path = image(workspace); data = bytearray(path.read_bytes()); offset = 8
    while offset < len(data):
        size = int.from_bytes(data[offset:offset+4], 'big')
        if data[offset+4:offset+8] == b'IDAT':
            data[offset+8:offset+8+size] = b'\xff' * size
            data[offset+8+size:offset+12+size] = zlib.crc32(data[offset+4:offset+8+size]).to_bytes(4, 'big')
            break
        offset += 12 + size
    else: pytest.fail('Synthetic PNG has no data chunk')
    path.write_bytes(data)
    with Image.open(path) as parsed: parsed.verify()
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'image')
    assert error.value.code == 'media_decode_failed' and error.value.phase == 'image_decode'


@pytest.mark.integration
def test_mp4_valid_boxes_with_broken_packets_are_not_decoded_success(workspace, tools, av_files):
    path = av_files['mp4']; data = bytearray(path.read_bytes()); offset = 0
    while offset < len(data):
        length = int.from_bytes(data[offset:offset+4], 'big')
        if data[offset+4:offset+8] == b'mdat':
            data[offset+8:offset+length] = b'\xff' * (length - 8)
            break
        offset += length
    else: pytest.fail('Synthetic MP4 has no data box')
    path.write_bytes(data)
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'video', tools)
    assert error.value.code == 'media_decode_failed' and error.value.phase in {'media_probe', 'media_decode'}


@pytest.mark.integration
def test_probe_protocol_shape_failure_remains_error(workspace, tools, av_files, monkeypatch):
    monkeypatch.setattr(m, '_run', lambda *a: b'{"streams":"FAKE_PRIVATE_SHAPE"}')
    with pytest.raises(m.MediaError) as error: inspect(workspace, av_files['mp3'], 'audio', tools)
    assert error.value.code == 'media_probe_protocol' and 'FAKE_PRIVATE' not in json.dumps(error.value.as_dict())


@pytest.mark.parametrize('variant', ['riff_length', 'data_length', 'unaligned_pcm'])
def test_pcm_truncation_and_uneven_frames_are_rejected(workspace, variant):
    path = wav(workspace); data = bytearray(path.read_bytes())
    if variant == 'riff_length': data = data[:-2]
    elif variant == 'data_length':
        data = data[:-2]; data[4:8] = (len(data)-8).to_bytes(4, 'little')
    else:
        data = data[:-1]; data[4:8] = (len(data)-8).to_bytes(4, 'little'); data[40:44] = (len(data)-44).to_bytes(4, 'little')
    path.write_bytes(data)
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'audio')
    assert error.value.code == 'media_incomplete'


@pytest.mark.integration
@pytest.mark.parametrize('fmt', ['mp3', 'mp4'])
def test_truncated_encoded_media_stops_before_probe(workspace, tools, av_files, monkeypatch, fmt):
    path = av_files[fmt]; path.write_bytes(path.read_bytes()[:-7])
    monkeypatch.setattr(m, '_run', lambda *a: pytest.fail('Probe of structurally incomplete media'))
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'audio' if fmt == 'mp3' else 'video', tools)
    assert error.value.code == 'media_incomplete'


@pytest.mark.parametrize('variant', ['bytes', 'leaf', 'ancestor'])
def test_byte_path_and_parent_races_stop_final_evidence(workspace, monkeypatch, variant):
    path = image(workspace, 'sub/test.png'); original = m._image
    def race(fd, container):
        result = original(fd, container)
        if variant == 'bytes': path.write_bytes(path.read_bytes()+b'changed')
        elif variant == 'leaf':
            data = path.read_bytes(); path.rename(path.with_name('old.png')); path.write_bytes(data)
        else:
            data = path.read_bytes(); path.parent.rename(workspace/'old_sub'); path.parent.mkdir(); path.write_bytes(data)
        return result
    monkeypatch.setattr(m, '_image', race)
    with pytest.raises(m.MediaError) as error: inspect(workspace, path, 'image')
    assert error.value.code == 'media_changed' and error.value.phase == 'final_file_recheck'


@pytest.mark.integration
def test_missing_and_changed_decoder_are_errors_not_artifact_rejections(workspace, tools, av_files):
    with pytest.raises(m.MediaError) as error: inspect(workspace, av_files['mp3'], 'audio')
    assert error.value.code == 'media_dependency_missing'
    changed = {k: dict(v) for k, v in tools.items()}; changed['ffprobe']['sha256'] = '0'*64
    with pytest.raises(m.MediaError) as error: inspect(workspace, av_files['mp3'], 'audio', changed)
    assert error.value.code == 'executable_changed'


@pytest.mark.parametrize('variant,code', [('timeout', 'media_decoder_timeout'), ('output', 'media_decoder_output_limit'), ('stderr', 'media_decode_failed'), ('crash', 'media_decoder_crashed')])
def test_process_limits_and_diagnostics_are_explicit_private(tmp_path, workspace, monkeypatch, variant, code):
    program = tmp_path/'decoder-fixture'
    body = "import time;time.sleep(2)" if variant == 'timeout' else "print('x'*2000)" if variant == 'output' else "import os,signal;os.kill(os.getpid(),signal.SIGTERM)" if variant == 'crash' else "import sys;sys.stderr.write('FAKE_PRIVATE_TAG_AND_PATH')"
    program.write_text(f'#!{sys.executable}\n{body}\n'); program.chmod(0o700)
    if variant == 'timeout': monkeypatch.setattr(m, 'PROCESS_SECONDS', 0.01)
    if variant == 'output': monkeypatch.setattr(m, 'PROCESS_OUTPUT', 100)
    path = image(workspace)
    with m._open_project_file(workspace, path.name) as (fd, _, _):
        with pytest.raises(m.MediaError) as error: m._run(str(program), [], fd, 'media_probe')
    assert error.value.code == code and 'FAKE_PRIVATE' not in json.dumps(error.value.as_dict())


def test_image_inspection_cli_uses_source_without_router_state_or_secrets(workspace, tmp_path):
    path = image(workspace); home = tmp_path/'unused-home'
    p = subprocess.run([sys.executable, '-m', 'agent_tool_maker', '--home', str(home), 'media', 'inspect',
                        '--workspace', str(workspace), '--file', path.name, '--kind', 'image', '--sha256', sha(path)],
                       cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT/'src')}, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)['status'] == 'artifact_verified' and not home.exists()


def test_direct_cli_negative_is_nonzero_and_adapter_keeps_explicit_condition(workspace, tmp_path, tools):
    path = image(workspace)
    base = [sys.executable, '-m', 'agent_tool_maker', '--home', str(tmp_path/'unused-home'), 'media']
    argv = ['--workspace', str(workspace), '--file', path.name, '--kind', 'image', '--sha256', '0'*64]
    env = {**os.environ, 'PYTHONPATH': str(ROOT/'src')}
    direct = subprocess.run([*base, 'inspect', *argv], cwd=ROOT, env=env, capture_output=True, text=True)
    assert direct.returncode == 2 and json.loads(direct.stdout)['error']['code'] == 'media_hash_mismatch'
    condition = subprocess.run([*base, 'adapter', '--pin', m.source_digest(), *argv], cwd=ROOT, env=env, capture_output=True, text=True)
    r = json.loads(condition.stdout)[0]['result']
    assert condition.returncode == 0 and r['status'] == 'artifact_rejected' and not r['valid'] and r['reason'] == 'media_hash_mismatch'
    assert r['phase'] == 'file_hash' and not r['outcome_uncertain']
    changed = subprocess.run([*base, 'adapter', '--pin', '0'*64, *argv], cwd=ROOT, env=env, capture_output=True, text=True)
    assert changed.returncode == 2 and json.loads(changed.stdout)['error']['code'] == 'definition_changed'


@pytest.mark.integration
def test_generated_cli_real_source_atm_checks_file_and_reuses_historical_evidence(router, workspace, tmp_path, tools):
    tool = b.manifest(tools); bundle = pack(tool, tmp_path/'bundle')
    assert validate_bundle(Path(bundle['directory']))['valid']
    install(router.state, router.catalog, Path(bundle['directory'])/'manifest.json', digest(tool))
    router.catalog = Catalog(router.state)
    executable = tmp_path/'source-atm'
    executable.write_text(f'#!{sys.executable}\nimport sys\nsys.path.insert(0,{str(ROOT/"src")!r})\nfrom agent_tool_maker.cli import main\nraise SystemExit(main())\n')
    executable.chmod(0o700); bind_cli(router.state, 'atm', str(executable))
    router.vault.get = lambda *a: pytest.fail('Credential read')
    path = image(workspace); inputs = {'file': path.name, 'kind': 'image', 'expected_sha256': sha(path)}
    input_path = workspace/'inputs.json'; input_path.write_text(json.dumps(inputs))
    argv = [sys.executable, str(Path(bundle['directory'])/'tool.py'), '--atm', str(executable), '--home', str(router.state.home),
            '--input', str(input_path), '--workspace', str(workspace), '--request-key', 'media-once', '--allow-code']
    process = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=True)
    job = json.loads(process.stdout); r = job['data']['result'][0]['result']
    assert job['status'] == 'completed' and r['status'] == 'artifact_verified' and r['valid']
    assert not job['data']['paid_granted'] and set(job['data']['permissions_granted']) == {'execute_code'}
    path.write_bytes(path.read_bytes()+b'changed')
    same = json.loads(subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    assert same['id'] == job['id'] and same['data']['result'] == job['data']['result']
    argv[argv.index('media-once')] = 'media-fresh'
    fresh = json.loads(subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    assert fresh['id'] != job['id'] and fresh['status'] == 'completed'
    rejected = fresh['data']['result'][0]['result']
    assert rejected['status'] == 'artifact_rejected' and not rejected['valid'] and rejected['reason'] == 'media_hash_mismatch'
    for artifact in job['data']['artifacts']:
        p = Path(artifact['path'])
        assert sha(p) == artifact['sha256'] and json.loads(p.read_bytes()) == job['data']['result']
