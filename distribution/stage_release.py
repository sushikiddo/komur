"""Stage an explicitly allowlisted source archive and the completed installer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    installer = root / 'dist-installer/Komur-Setup-1.2.0-x64.exe'
    if not installer.is_file():
        raise RuntimeError('Build and verify the installer first.')
    files = [p for p in root.iterdir() if p.is_file() and p.suffix in {'.py', '.spec'}]
    files += [root / name for name in ('KULLANIM-AI.md', 'TEST_SONUCLARI-v4.md', 'NASIL-PAYLASILIR.txt',
                                     'requirements-voice.txt', 'version_info.txt')]
    for folder, suffixes in (('tests', {'.py'}), ('distribution', {'.py', '.ps1', '.iss', '.txt'}),
                             ('assets', {'.png', '.wav', '.mp3', '.json', '.ico'})):
        files += [p for p in (root / folder).rglob('*') if p.is_file() and p.suffix in suffixes]
    archive = root / 'Komur-Kaynak-v4.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(set(files)):
            output.write(path, Path('Komur-Kaynak-v4') / path.relative_to(root))
    checksum = installer.with_suffix(installer.suffix + '.sha256')
    checksum.write_text(f'{digest(installer)}  {installer.name}\n', encoding='ascii')
    desktop = Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'Desktop'
    for path in (installer, checksum, archive):
        shutil.copy2(path, desktop / path.name)
        if digest(path) != digest(desktop / path.name):
            raise RuntimeError('Release copy failed verification: ' + path.name)
    manifest = {'version': '1.2.0', 'published_online': False,
                'files': [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)}
                          for p in (installer, root / 'dist/Komur.exe', archive)]}
    (root / 'release-manifest-v4.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
