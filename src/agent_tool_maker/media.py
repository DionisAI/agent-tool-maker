"""Project-local decoded media evidence. No browser, network, vault or task claims."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
import warnings
import wave

from .errors import RouterError

MAX_BYTES = 512 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SECONDS = 3600
PROCESS_SECONDS = 120
PROCESS_OUTPUT = 128 * 1024
EXTENSIONS = {'.png': ('image', 'png'), '.jpg': ('image', 'jpeg'), '.jpeg': ('image', 'jpeg'),
              '.webp': ('image', 'webp'), '.wav': ('audio', 'wav'), '.mp3': ('audio', 'mp3'),
              '.mp4': ('video', 'mp4')}
REJECTIONS = {'media_path_invalid', 'media_size_limit', 'media_hash_mismatch', 'media_format_mismatch',
              'media_kind_mismatch', 'media_incomplete', 'media_decode_failed', 'media_limit',
              'media_changed', 'media_unsupported'}


class MediaError(RouterError):
    def __init__(self, code, message, phase):
        super().__init__(code, message)
        self.phase = phase

    def as_dict(self):
        return {**super().as_dict(), 'phase': self.phase}


def fail(code, message, phase):
    raise MediaError(code, message, phase)


def source_digest():
    path = Path(__file__)
    if path.is_symlink() or not path.is_file():
        fail('definition_changed', 'Review the regular media-validator source.', 'source_pin')
    return hashlib.sha256(b'media.py\0' + path.read_bytes() + b'\0').hexdigest()


def _snapshot(fd):
    s = os.fstat(fd)
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


@contextmanager
def _open_project_file(workspace, file):
    raw = str(workspace)
    if (not raw.startswith('/') or raw == '/' or os.path.normpath(raw) != raw or
            not isinstance(file, str) or len(file) > 1024 or file.startswith('/') or
            any(p in {'', '.', '..'} for p in file.split('/')) or
            any(ord(c) < 32 for c in raw + file)):
        fail('media_path_invalid', 'Select one canonical project-local relative media file.', 'file_eligibility')
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
        fail('unsupported_backend', 'Project media inspection requires no-follow POSIX file descriptors.', 'file_eligibility')
    with ExitStack() as stack:
        try:
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            directory = os.open('/', flags | os.O_DIRECTORY)
            stack.callback(os.close, directory)
            for part in (*Path(raw).parts[1:], *file.split('/')[:-1]):
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                stack.callback(os.close, directory)
            leaf = file.split('/')[-1]
            fd = os.open(leaf, flags | os.O_NONBLOCK, dir_fd=directory)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                fail('media_path_invalid', 'Select a single-link regular media file, not a special file or alias.', 'file_eligibility')
        except OSError:
            fail('media_path_invalid', 'Project media path is missing, inaccessible or linked.', 'file_eligibility')
        if not 0 < info.st_size <= MAX_BYTES:
            fail('media_size_limit', 'Media file must be nonempty and within the declared byte limit.', 'file_eligibility')
        yield fd, directory, leaf


def _hash(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    total = 0
    digest = hashlib.sha256()
    while block := os.read(fd, 1024 * 1024):
        total += len(block)
        if total > MAX_BYTES:
            fail('media_size_limit', 'Media grew beyond the declared byte limit.', 'file_hash')
        digest.update(block)
    return digest.hexdigest()


def _read(fd, offset, size):
    return os.pread(fd, size, offset)


def _structure(fd, container, size):
    head = _read(fd, 0, 32)
    if container == 'png':
        if not head.startswith(b'\x89PNG\r\n\x1a\n'):
            fail('media_format_mismatch', 'PNG signature does not match the selected extension.', 'container')
        if size < 20 or _read(fd, size - 12, 12) != b'\x00\x00\x00\x00IEND\xaeB`\x82':
            fail('media_incomplete', 'PNG has no complete terminal IEND chunk.', 'container')
    elif container == 'jpeg':
        if not head.startswith(b'\xff\xd8\xff'):
            fail('media_format_mismatch', 'JPEG signature does not match the selected extension.', 'container')
        if _read(fd, size - 2, 2) != b'\xff\xd9':
            fail('media_incomplete', 'JPEG has no terminal end-of-image marker.', 'container')
    elif container in {'wav', 'webp'}:
        if head[:4] != b'RIFF' or head[8:12] != (b'WAVE' if container == 'wav' else b'WEBP'):
            fail('media_format_mismatch', 'RIFF type does not match the selected extension.', 'container')
        if int.from_bytes(head[4:8], 'little') + 8 != size:
            fail('media_incomplete', 'RIFF byte length does not match the complete file.', 'container')
    elif container == 'mp4':
        if head[4:8] != b'ftyp':
            fail('media_format_mismatch', 'MP4 has no leading file-type box.', 'container')
        offset = 0; boxes = 0; present = set()
        while offset < size:
            header = _read(fd, offset, 16)
            if len(header) < 8:
                fail('media_incomplete', 'MP4 has an incomplete box header.', 'container')
            length = int.from_bytes(header[:4], 'big'); minimum = 8
            if length == 1:
                if len(header) < 16:
                    fail('media_incomplete', 'MP4 has an incomplete extended box header.', 'container')
                length = int.from_bytes(header[8:16], 'big'); minimum = 16
            elif length == 0:
                length = size - offset
            if length < minimum or offset + length > size:
                fail('media_incomplete', 'MP4 box length exceeds available file bytes.', 'container')
            present.add(header[4:8]); boxes += 1
            if boxes > 10000:
                fail('media_limit', 'MP4 exceeds the declared container-box limit.', 'container')
            offset += length
        if not {b'ftyp', b'moov', b'mdat'} <= present:
            fail('media_incomplete', 'MP4 lacks required metadata or media-data boxes.', 'container')
    elif container == 'mp3':
        return _mp3_frames(fd, size)
    return None


def _mp3_frames(fd, size):
    offset = 0; end = size; frames = 0; rate = None
    if _read(fd, 0, 3) == b'ID3':
        header = _read(fd, 0, 10)
        if len(header) != 10 or header[3] not in {2, 3, 4} or any(v & 128 for v in header[6:10]):
            fail('media_incomplete', 'MP3 has an invalid ID3 header.', 'container')
        if header[3] == 4 and header[5] & 16:
            fail('media_unsupported', 'ID3 footer variants require a separate validation contract.', 'container')
        offset = 10 + sum(v << shift for v, shift in zip(header[6:10], [21, 14, 7, 0]))
        if offset >= size:
            fail('media_incomplete', 'MP3 tag consumes the available media bytes.', 'container')
    if size >= 128 and _read(fd, size - 128, 3) == b'TAG':
        end -= 128
    while offset < end:
        data = _read(fd, offset, 4)
        if len(data) != 4:
            fail('media_incomplete', 'MP3 ends inside a frame header.', 'container')
        header = int.from_bytes(data, 'big')
        version = (header >> 19) & 3; layer = (header >> 17) & 3
        bitrate = (header >> 12) & 15; sample = (header >> 10) & 3
        if header >> 21 != 0x7ff or version == 1 or layer != 1 or sample == 3:
            fail('media_format_mismatch', 'MP3 contains an unknown Layer-III frame boundary.', 'container')
        if bitrate in {0, 15}:
            fail('media_unsupported', 'Free/reserved MP3 bitrates need a separate frame contract.', 'container')
        kbps = ([0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320] if version == 3
                else [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160])[bitrate]
        sample_rate = [44100, 48000, 32000][sample] // (1 if version == 3 else 2 if version == 2 else 4)
        if rate is not None and rate != sample_rate:
            fail('media_unsupported', 'Changing MP3 frame sample rates need a separate contract.', 'container')
        rate = sample_rate
        length = (144 if version == 3 else 72) * kbps * 1000 // sample_rate + ((header >> 9) & 1)
        if offset + length > end:
            fail('media_incomplete', 'MP3 ends inside a complete audio frame.', 'container')
        offset += length; frames += 1
    if not frames:
        fail('media_incomplete', 'MP3 contains no complete audio frames.', 'container')
    return frames


def _image(fd, container):
    from PIL import Image, UnidentifiedImageError
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            for verify in (True, False):
                os.lseek(fd, 0, os.SEEK_SET)
                with os.fdopen(os.dup(fd), 'rb') as stream, Image.open(stream) as image:
                    if image.format != container.upper():
                        fail('media_format_mismatch', 'Decoded image type differs from its extension.', 'image_decode')
                    if image.width * image.height > MAX_PIXELS:
                        fail('media_limit', 'Image exceeds the declared pixel limit.', 'image_decode')
                    if getattr(image, 'n_frames', 1) != 1:
                        fail('media_unsupported', 'Animated images need a separate delivery contract.', 'image_decode')
                    result = {'width': image.width, 'height': image.height, 'pixel_mode': image.mode,
                              'frame_count': 1, 'duration_seconds': None}
                    image.verify() if verify else image.load()
        return result
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        fail('media_limit', 'Image exceeds decoder size limits.', 'image_decode')
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        fail('media_decode_failed', 'Image structure or complete pixel decoding failed.', 'image_decode')


def _wav(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        with os.fdopen(os.dup(fd), 'rb') as stream, wave.open(stream) as audio:
            channels, width, rate, frames = audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()
            if audio.getcomptype() != 'NONE' or not frames:
                fail('media_unsupported', 'Select nonempty uncompressed PCM WAV.', 'audio_decode')
            if not 1 <= channels <= 16 or not 1 <= width <= 4 or not 8000 <= rate <= 384000 or frames / rate > MAX_SECONDS:
                fail('media_limit', 'PCM WAV parameters exceed declared limits.', 'audio_decode')
            offset = 12; data_length = None; chunks = 0; size = os.fstat(fd).st_size
            while offset < size:
                header = _read(fd, offset, 8)
                if len(header) != 8:
                    fail('media_incomplete', 'WAV has an incomplete chunk header.', 'audio_decode')
                length = int.from_bytes(header[4:8], 'little')
                offset += 8 + length + (length & 1); chunks += 1
                if offset > size or chunks > 10000:
                    fail('media_incomplete', 'WAV chunks exceed available file bytes.', 'audio_decode')
                if header[:4] == b'data':
                    if data_length is not None:
                        fail('media_unsupported', 'Multiple PCM data chunks need a separate contract.', 'audio_decode')
                    data_length = length
            if data_length != frames * channels * width:
                fail('media_incomplete', 'WAV PCM byte length is not an exact complete-frame count.', 'audio_decode')
            remaining = frames
            while remaining:
                count = min(remaining, 65536)
                if len(audio.readframes(count)) != count * width * channels:
                    fail('media_incomplete', 'WAV ends before all declared PCM frames.', 'audio_decode')
                remaining -= count
            return {'sample_rate_hz': rate, 'channels': channels, 'sample_width_bytes': width,
                    'frame_count': frames, 'duration_seconds': frames / rate, 'duration_source': 'pcm_frames'}
    except (wave.Error, EOFError, OSError):
        fail('media_decode_failed', 'Complete PCM WAV parsing failed.', 'audio_decode')


def _tool(path, expected, phase):
    if not isinstance(path, str) or not path.startswith('/') or not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
        fail('media_dependency_missing', 'Select reviewed absolute FFmpeg tools and exact hashes.', phase)
    p = Path(path)
    try:
        if p.is_symlink() or not p.is_file() or not os.access(p, os.X_OK):
            fail('media_dependency_missing', 'A regular reviewed executable is required.', phase)
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            fail('executable_changed', 'Review the changed media decoder before executing it.', phase)
    except OSError:
        fail('media_dependency_missing', 'The reviewed media decoder is inaccessible.', phase)
    return str(p)


def _run(executable, argv, fd, phase):
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        proc = subprocess.Popen([executable, *argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, pass_fds=(fd,), shell=False, start_new_session=True,
                                env={'LANG': 'C', 'LC_ALL': 'C', 'AV_LOG_FORCE_NOCOLOR': '1'})
    except OSError:
        fail('media_decoder_start_failed', 'The reviewed media process did not start.', phase)
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    deadline = time.monotonic() + PROCESS_SECONDS
    try:
        with selectors.DefaultSelector() as select:
            for name, pipe in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
                select.register(pipe, selectors.EVENT_READ, name)
            while select.get_map():
                left = deadline - time.monotonic()
                if left <= 0:
                    fail('media_decoder_timeout', 'Media validation exceeded its process deadline.', phase)
                for key, _ in select.select(min(left, 0.1)):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        select.unregister(key.fileobj)
                    else:
                        buffers[key.data].extend(block)
                        if sum(map(len, buffers.values())) > PROCESS_OUTPUT:
                            fail('media_decoder_output_limit', 'Media diagnostics exceeded their byte limit.', phase)
            try:
                proc.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                fail('media_decoder_timeout', 'Media validation exceeded its process deadline.', phase)
        if proc.returncode < 0:
            fail('media_decoder_crashed', 'The media decoder terminated by signal; inspect its installation.', phase)
        if proc.returncode or buffers['stderr']:
            fail('media_decode_failed', 'The decoder reported invalid media; raw diagnostics remain suppressed.', phase)
        return bytes(buffers['stdout'])
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        proc.stdout.close(); proc.stderr.close()


def _number(value, phase):
    if isinstance(value, bool):
        fail('media_unsupported', 'Media duration must be a numeric observation.', phase)
    try:
        number = float(value)
    except (ValueError, TypeError):
        fail('media_unsupported', 'Media has no verified positive duration.', phase)
    if not math.isfinite(number) or number <= 0 or number > MAX_SECONDS:
        fail('media_limit', 'Media duration exceeds declared limits or is invalid.', phase)
    return number


def _av(fd, container, kind, toolchain, frames):
    if not isinstance(toolchain, dict) or any(not isinstance(toolchain.get(k), dict) for k in ('ffprobe', 'ffmpeg')):
        fail('media_dependency_missing', 'Select the reviewed media toolchain.', 'decoder_pin')
    selected = {k: _tool(*(toolchain.get(k, {}).get(v) for v in ('path', 'sha256')), 'decoder_pin')
                for k in ('ffprobe', 'ffmpeg')}
    input_args = ['-protocol_whitelist', 'fd', '-format_whitelist', 'mp3' if container == 'mp3' else 'mov',
                  '-f', 'mp3' if container == 'mp3' else 'mov', '-threads', '2']
    if container == 'mp4':
        input_args += ['-enable_drefs', '0', '-use_absolute_path', '0']
    input_args += ['-fd', str(fd), '-i', 'fd:']
    raw = _run(selected['ffprobe'], ['-v', 'error', *input_args, '-show_entries',
               'format=format_name,duration:stream=index,codec_type,codec_name,width,height,sample_rate,channels:stream_disposition=attached_pic',
               '-of', 'json'], fd, 'media_probe')
    try:
        parsed = json.loads(raw)
        streams = parsed['streams']; fmt = parsed['format']; names = fmt['format_name'].split(',')
        if not isinstance(streams, list) or not 1 <= len(streams) <= 2:
            fail('media_unsupported', 'Media stream layout needs a separate contract.', 'media_probe')
        if (container == 'mp3' and names != ['mp3']) or (container == 'mp4' and 'mp4' not in names):
            fail('media_format_mismatch', 'Probed container does not match the selected format.', 'media_probe')
        duration = _number(fmt.get('duration'), 'media_probe')
        result = {'duration_seconds': duration, 'duration_source': 'container_metadata', 'streams': []}
        types = [s['codec_type'] for s in streams]
        if (kind == 'audio' and types != ['audio']) or (kind == 'video' and (types.count('video') != 1 or types.count('audio') > 1 or set(types) - {'video', 'audio'})):
            fail('media_kind_mismatch', 'Media streams differ from the requested output kind.', 'media_probe')
        for s in streams:
            if not re.fullmatch('[a-z0-9_]{1,48}', s['codec_name']) or s.get('disposition', {}).get('attached_pic', 0):
                fail('media_unsupported', 'Unknown codecs or cover-only video need a separate contract.', 'media_probe')
            entry = {'type': s['codec_type'], 'codec': s['codec_name']}
            if s['codec_type'] == 'video':
                w, h = s['width'], s['height']
                if type(w) is not int or type(h) is not int or w <= 0 or h <= 0 or w * h > MAX_PIXELS:
                    fail('media_limit', 'Video dimensions exceed declared limits.', 'media_probe')
                entry.update(width=w, height=h)
            else:
                rate, channels = int(s['sample_rate']), s['channels']
                if type(channels) is not int or not 1 <= channels <= 16 or not 8000 <= rate <= 384000:
                    fail('media_limit', 'Audio parameters exceed declared limits.', 'media_probe')
                entry.update(sample_rate_hz=rate, channels=channels)
            result['streams'].append(entry)
    except (ValueError, UnicodeError, KeyError, TypeError, AttributeError):
        fail('media_probe_protocol', 'Media probe returned an unsupported JSON shape.', 'media_probe')
    maps = ['-map', '0:a:0'] if kind == 'audio' else ['-map', '0:v:0', '-map', '0:a:0?']
    progress = _run(selected['ffmpeg'], ['-nostdin', '-v', 'error', '-xerror', *input_args, *maps,
                    '-threads', '2', '-stats_period', '3600', '-progress', 'pipe:1', '-f', 'null', '-'], fd, 'media_decode')
    try:
        values = dict(line.split('=', 1) for line in progress.decode('ascii').splitlines())
        if values.get('progress') != 'end' or int(values.get('out_time_us', '0')) <= 0 or (kind == 'video' and int(values.get('frame', '0')) <= 0):
            fail('media_decode_failed', 'Complete decode produced no positive media output.', 'media_decode')
    except (ValueError, UnicodeError):
        fail('media_probe_protocol', 'Decoder progress returned an unsupported shape.', 'media_decode')
    for k in selected:
        _tool(toolchain[k]['path'], toolchain[k]['sha256'], 'decoder_recheck')
    result['decoded_frame_count'] = int(values['frame']) if kind == 'video' else None
    result['decoded_output_time_seconds'] = _number(int(values['out_time_us']) / 1_000_000, 'media_decode')
    if frames is not None:
        result['container_frame_count'] = frames
    result['decoder_sha256'] = {k: toolchain[k]['sha256'] for k in selected}
    return result


def inspect_media(workspace, file, kind, expected_sha256, toolchain=None):
    if not isinstance(kind, str) or kind not in {'image', 'audio', 'video'} or not isinstance(expected_sha256, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha256):
        fail('invalid_argument', 'Use an exact media kind and expected lowercase SHA256.', 'arguments')
    extension = Path(file).suffix.lower() if isinstance(file, str) else ''
    if extension not in EXTENSIONS:
        fail('media_unsupported', 'Select PNG/JPEG/WebP, PCM WAV/MP3 or MP4.', 'file_eligibility')
    expected_kind, container = EXTENSIONS[extension]
    if expected_kind != kind:
        fail('media_kind_mismatch', 'Media extension differs from the requested output kind.', 'file_eligibility')
    with _open_project_file(workspace, file) as (fd, parent, leaf):
        before = _snapshot(fd)
        if _hash(fd) != expected_sha256:
            fail('media_hash_mismatch', 'Selected media bytes differ from the expected digest.', 'file_hash')
        frames = _structure(fd, container, before[2])
        metadata = _image(fd, container) if kind == 'image' else _wav(fd) if container == 'wav' else _av(fd, container, kind, toolchain or {}, frames)
        if _hash(fd) != expected_sha256 or _snapshot(fd) != before:
            fail('media_changed', 'Media bytes or identity changed during validation.', 'final_file_recheck')
        try:
            with _open_project_file(workspace, file) as (check, _, _):
                if _snapshot(check) != before:
                    fail('media_changed', 'Selected media path changed during validation.', 'final_file_recheck')
        except MediaError as error:
            if error.code not in {'media_path_invalid', 'media_size_limit'}:
                raise
            fail('media_changed', 'Selected media path changed during validation.', 'final_file_recheck')
    return {'status': 'artifact_verified', 'valid': True, 'kind': kind, 'format': container, 'file': file,
            'bytes': before[2], 'sha256': expected_sha256, 'media': metadata, 'complete_decode_verified': True,
            'source': 'local_file', 'validator_sha256': source_digest(), 'task_association_verified': False,
            'provider_generation_verified': False, 'download_verified': False, 'network_calls': 0,
            'credentials_read': False, 'upload_started': False, 'generation_submitted': False, 'paid_submitted': False}


def add_commands(sub):
    root = sub.add_parser('media', help='Inspect a selected local media artifact; no provider or task claims')
    commands = root.add_subparsers(dest='operation', required=True)
    for name in ('inspect', 'adapter'):
        command = commands.add_parser(name, help=argparse.SUPPRESS if name == 'adapter' else 'Verify project media bytes and decoding')
        command.add_argument('--workspace', required=True)
        command.add_argument('--file', required=True)
        command.add_argument('--kind', required=True, choices=['image', 'audio', 'video'])
        command.add_argument('--sha256', required=True)
        if name == 'adapter':
            command.add_argument('--pin', required=True)
        for tool in ('ffmpeg', 'ffprobe'):
            command.add_argument('--' + tool)
            command.add_argument('--' + tool + '-sha256')


def dispatch(args):
    if args.operation == 'adapter' and args.pin != source_digest():
        fail('definition_changed', 'Review the changed media validation definition.', 'source_pin')
    toolchain = {k: {'path': getattr(args, k), 'sha256': getattr(args, k + '_sha256')} for k in ('ffmpeg', 'ffprobe')}
    try:
        result = inspect_media(args.workspace, args.file, args.kind, args.sha256, toolchain)
    except MediaError as error:
        if args.operation != 'adapter' or error.code not in REJECTIONS:
            raise
        result = {'status': 'artifact_rejected', 'valid': False, 'reason': error.code, 'phase': error.phase,
                  'outcome_uncertain': False, 'source': 'local_file', 'network_calls': 0, 'credentials_read': False,
                  'task_association_verified': False, 'provider_generation_verified': False, 'download_verified': False,
                  'upload_started': False, 'generation_submitted': False, 'paid_submitted': False}
    return [{'result': result}] if args.operation == 'adapter' else result
