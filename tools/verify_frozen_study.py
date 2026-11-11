"""Verify the exact recorded manuscript study, without rerunning simulations."""
from pathlib import Path
import hashlib
import json


def main():
    root = Path(__file__).resolve().parents[1]
    study = root/'studies/manuscript_revision'
    checked = 0
    for line in (study/'SHA256SUMS.txt').read_text().splitlines():
        expected, name = line.split('  ', 1)
        actual = hashlib.sha256((study/name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Frozen study mismatch: {name}')
        checked += 1
    record = json.loads((study/'results/revision_validation.json').read_text())
    for name, metadata in record['documents'].items():
        if hashlib.sha256((root/'docs'/name).read_bytes()).hexdigest() != metadata['sha256']:
            raise SystemExit(f'Manuscript mismatch: {name}')
    print(json.dumps({'status':'passed','frozen_files':checked,'manuscript_files':2}))


if __name__ == '__main__':
    main()
