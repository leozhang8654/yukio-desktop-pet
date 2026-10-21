"""Verify preview/Windows source-kit assets; does not claim Windows execution."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import struct
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_macho(path):
    data = bytearray(path.read_bytes())
    assert struct.unpack_from('<I', data)[0] == 0xFEEDFACF, 'expected thin 64-bit preview binary'
    offset = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, offset)
        if command == 0x19 and data[offset+8:offset+24].rstrip(b'\0') == b'__LINKEDIT':
            # codesign leaves different VM reservation sizes after stripping;
            # normalize just that reservation, preserving every content byte.
            unsigned_size = struct.unpack_from('<Q', data, offset+48)[0]
            struct.pack_into('<Q', data, offset+32, unsigned_size)
        offset += size
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--pages', type=Path, required=True)
    parser.add_argument('--mac-app', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--windows-kit', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    mac = args.mac_app/'Contents/Resources/Assets'
    windows = args.windows_kit/'YukioWin/Assets'
    records = {}
    for folder in ['interaction', 'base', 'activities']:
        for source in (args.assets/folder).iterdir():
            if not source.is_file():
                continue
            relative = source.relative_to(args.assets)
            digest = sha(source)
            assert digest == sha(mac/relative) == sha(windows/relative), str(relative)
            records[str(relative)] = digest
    for source in (args.pages/'motion/windows-pages').rglob('*'):
        if source.is_file():
            relative = source.relative_to(args.pages)
            digest = sha(source)
            assert digest == sha(mac/relative) == sha(windows/relative), str(relative)
            records[str(relative)] = digest
    pages = json.loads((args.pages/'motion/windows-pages/manifest.json').read_text())
    assert pages['motionSha256'] == sha(args.assets/'motion/motion.json')
    assert pages['interactionSha256'] == sha(args.assets/'interaction/interaction.json')
    daily = {}
    for before in (args.baseline/'motion').iterdir():
        if before.is_file():
            relative = Path('motion')/before.name
            assert sha(before) == sha(args.assets/relative) == sha(mac/relative), str(relative)
            daily[str(relative)] = sha(before)
    packaged_binary = args.mac_app/'Contents/MacOS/YukioPlayer'
    # Bundle signing changes LC_CODE_SIGNATURE. Compare disposable unsigned
    # copies, leaving both the built executable and signed bundle untouched.
    with tempfile.TemporaryDirectory(prefix='yukio-signature-compare-') as temporary:
        copies = [Path(temporary)/name for name in ['build', 'bundle']]
        for original, copy in zip([args.binary, packaged_binary], copies):
            shutil.copy2(original, copy)
            subprocess.run(['codesign', '--remove-signature', str(copy)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert normalized_macho(copies[0]) == normalized_macho(copies[1]), 'Mach-O contents differ'
        executable_digest = normalized_macho(copies[0])
    python_sources = {}
    project = Path(__file__).resolve().parents[3]
    for source in (project/'YukioWin/yukio').glob('*.py'):
        assert sha(source) == sha(args.windows_kit/'YukioWin/yukio'/source.name), source.name
        python_sources[source.name] = sha(source)
    report = {'windowsPythonSourceHashes': python_sources, 'passed': True, 'normalizedMachOSha256': executable_digest,
              'normalization': 'remove signatures from temporary copies; normalize only __LINKEDIT VM reservation to unsigned file size',
              'buildBinarySha256': sha(args.binary), 'signedBundleBinarySha256': sha(packaged_binary),
              'sharedAssetHashes': records, 'unchangedDailyHashes': daily,
              'windowsNativeExecution': 'pending; this verifies files only'}
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: {len(records)} shared files, {len(daily)} unchanged daily files, matching macOS binary')


if __name__ == '__main__':
    main()
