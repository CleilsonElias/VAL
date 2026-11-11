"""Create a deterministic source ZIP and refresh its SHA-256 inventory."""
from pathlib import Path
import argparse
import hashlib
import zipfile


def included(path, root):
    rel = path.relative_to(root)
    return (path.is_file() and path.name != 'SHA256SUMS.txt' or path == root/'studies/manuscript_revision/SHA256SUMS.txt') and not any(
        x in {'.git', '__pycache__', '.venv', 'build', 'dist', 'val_demo', 'local_results'} or x.endswith('.egg-info')
        for x in rel.parts) and path.suffix not in {'.pyc', '.pyo', '.sqlite'}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    output = Path(parser.parse_args().output).resolve()
    if output == root or root in output.parents:
        parser.error('archive output must be outside the source directory')
    files = sorted(p for p in root.rglob('*') if included(p, root))
    inventory = root/'SHA256SUMS.txt'
    inventory.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files+[inventory]):
            info = zipfile.ZipInfo('VAL/'+path.relative_to(root).as_posix(), (2026,11,11,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('archive integrity check failed')
    print(f'{len(files)+1} files; {output.stat().st_size} bytes; sha256 {hashlib.sha256(output.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
