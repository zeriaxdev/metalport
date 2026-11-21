"""Compile MSL with Metal itself; cache successful checks by source and compiler identity."""
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / 'cache' / 'metal-check'


class MetalCheckUnavailable(RuntimeError):
    pass


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def checker():
    source = HERE / 'mslcheck.m'
    identity = hashlib.sha256(source.read_bytes() + Path(__file__).read_bytes() + platform.platform().encode()).hexdigest()
    binary = CACHE / identity / 'mslcheck'
    if not binary.is_file():
        binary.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=binary.parent) as temporary:
            built = Path(temporary) / 'mslcheck'
            try:
                result = subprocess.run(['clang', '-fobjc-arc', '-Wno-deprecated-declarations',
                                         '-framework', 'Foundation', '-framework', 'Metal',
                                         str(source), '-o', str(built)], capture_output=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise MetalCheckUnavailable(f'Cannot build Metal checker: {error}') from error
            if result.returncode:
                raise MetalCheckUnavailable(result.stderr.decode(errors='replace'))
            os.replace(built, binary)
    return binary


def validate_sources(sources):
    """Return {source SHA256: compiler error} for invalid sources. Infrastructure errors raise."""
    unique = {hashlib.sha256(source).hexdigest(): source for source in sources}
    if not unique:
        return {}
    binary = checker()
    pending = []
    for digest, source in unique.items():
        path = binary.parent / (digest + '.metal')
        if path.with_suffix('.ok').is_file() and path.is_file() and path.read_bytes() == source:
            continue
        atomic_write(path, source)
        pending.append(path)
    failures = {}
    for start in range(0, len(pending), 128):
        batch = pending[start:start + 128]
        try:
            result = subprocess.run([str(binary), *map(str, batch)], capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise MetalCheckUnavailable(f'Metal checker failed: {error}') from error
        if result.returncode not in (0, 1):
            raise MetalCheckUnavailable(result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
        try:
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            assert len(rows) == len(batch)
            assert {row['path'] for row in rows} == set(map(str, batch))
            assert all(type(row['ok']) is bool and isinstance(row['error'], str) for row in rows)
            assert (result.returncode == 0) == all(row['ok'] for row in rows)
        except (ValueError, KeyError, AssertionError, TypeError) as error:
            raise MetalCheckUnavailable('Incomplete/invalid response from Metal checker') from error
        for row in rows:
            path = Path(row['path'])
            if row['ok']:
                atomic_write(path.with_suffix('.ok'), b'ok\n')
            else:
                failures[path.stem] = row['error']
    return failures


def require_valid(sources):
    failures = validate_sources(sources)
    if failures:
        raise ValueError(f'Metal compilation failed for {len(failures)} program(s): ' + next(iter(failures.values())))
