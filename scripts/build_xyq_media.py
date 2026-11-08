"""Compile local XYQ media evidence separately from the eighteen website tools."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from agent_tool_maker import extensions
from agent_tool_maker.maker import validate_manifest
from agent_tool_maker.media import source_digest
if not Path(extensions.__file__).resolve().is_relative_to(ROOT/'src'):
    raise RuntimeError('Use this reviewed repository source in a fresh process.')


def toolchain(ffprobe=None, ffmpeg=None):
    result = {}
    for name, selected in [('ffprobe', ffprobe), ('ffmpeg', ffmpeg)]:
        raw = selected or shutil.which(name)
        if not raw:
            raise RuntimeError('Select an existing reviewed FFmpeg toolchain; no implicit installation.')
        path = Path(raw).resolve(strict=True)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError('Select regular executable media tools.')
        result[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def manifest(selected):
    argv = ['media', 'adapter', '--pin', source_digest(), '--workspace', {'workspace': ''},
            '--file', {'input': 'file'}, '--kind', {'input': 'kind'}, '--sha256', {'input': 'expected_sha256'}]
    for name in ('ffprobe', 'ffmpeg'):
        argv += ['--'+name, selected[name]['path'], '--'+name+'-sha256', selected[name]['sha256']]
    return validate_manifest({'id': 'xyq.media.artifact_inspect', 'provider': 'xyq',
        'title': '小云雀媒体 · 本地产物校验', 'capabilities': ['media-validation', 'artifact_inspect'],
        'adapter': 'command', 'executable': 'atm', 'paid': False, 'permissions': ['execute_code'],
        'schema': {'type': 'object', 'properties': {
            'file': {'type': 'string', 'minLength': 1, 'maxLength': 1024},
            'kind': {'enum': ['image', 'audio', 'video']},
            'expected_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}},
            'required': ['file', 'kind', 'expected_sha256'], 'additionalProperties': False},
        'example': {'file': 'outputs/test.png', 'kind': 'image', 'expected_sha256': '0'*64},
        'command': {'argv': argv, 'output': 'json', 'timeout': 300},
        'sources': ['https://ffmpeg.org/ffprobe.html', 'https://pillow.readthedocs.io/en/stable/reference/Image.html'],
        'checked_on': '2026-10-07',
        'notes': 'Only the selected project-relative regular file. Validate exact expected SHA, container completeness and actual decoding, then reopen the complete path and recheck identity/hash. Image/PCM inspection is local; MP3/MP4 use hash-pinned executables, fd-only input protocols and no MOV external references. Bounded files/processes/metadata; no browser, auth, provider request, upload, generation, spending or implicit dependency installation.',
        'completion': 'artifact_verified proves local bytes/decoding only, not provider task association or download. artifact_rejected is an explicit completed condition check with valid=false/reason/phase, not a valid media artifact. Dependency/execution/protocol failures remain errors. Same-key reuse is historical evidence; a new key is needed to check current file bytes.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ffprobe'); parser.add_argument('--ffmpeg')
    args = parser.parse_args()
    selected = toolchain(args.ffprobe, args.ffmpeg)
    bundle = extensions.pack(manifest(selected), args.out/'artifact_inspect')
    print(json.dumps({'status': 'compiled', 'scope': 'local-media-evidence', 'validator_sha256': source_digest(),
                      'toolchain': selected, 'bundles': [bundle], 'website_tools_changed': False,
                      'provider_delivery_verified': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
