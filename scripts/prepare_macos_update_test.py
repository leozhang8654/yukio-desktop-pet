#!/usr/bin/env python3
"""Create isolated, signed upgrade fixtures without touching the production key.

Run on macOS against a packaged Yukio.app, then serve OUT/feed on 127.0.0.1:18744
and open OUT/baseline/Yukio.app. Never distribute these test bundles.
"""
import argparse
import hashlib
from pathlib import Path
import plistlib
import subprocess
import tempfile
import xml.etree.ElementTree as ET

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--sign-tool', type=Path, required=True)
a = p.parse_args()
if a.out.exists():
    raise SystemExit('Use a new output directory for each validation round')
a.out.mkdir(parents=True)
feed = a.out / 'feed'
feed.mkdir()
ns = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
ET.register_namespace('sparkle', ns)
with tempfile.TemporaryDirectory(prefix='yukio-test-signing-') as key_dir:
    key_dir = Path(key_dir)
    swift = key_dir / 'generate.swift'
    swift.write_text('''import Foundation
import CryptoKit
let dir = URL(fileURLWithPath: CommandLine.arguments[1])
let key = Curve25519.Signing.PrivateKey()
try key.rawRepresentation.base64EncodedData().write(to: dir.appendingPathComponent("private"))
try key.publicKey.rawRepresentation.base64EncodedData().write(to: dir.appendingPathComponent("public"))
''')
    subprocess.run(['swift', str(swift), str(key_dir)], check=True)
    (key_dir / 'private').chmod(0o600)
    public = (key_dir / 'public').read_text()
    target_info = plistlib.loads((a.app / 'Contents/Info.plist').read_bytes())
    for name in ('baseline', 'target'):
        bundle = a.out / name / 'Yukio.app'
        subprocess.run(['ditto', str(a.app), str(bundle)], check=True)
        info = dict(target_info)
        info.update(CFBundleIdentifier='local.yukio.update-validation',
            CFBundleName='Yukio Update Validation', CFBundleDisplayName='Yukio Update Validation',
            SUPublicEDKey=public, SUFeedURL='http://127.0.0.1:18744/appcast.xml',
            SURequireSignedFeed=True, SUVerifyUpdateBeforeExtraction=True,
            NSAppTransportSecurity={'NSAllowsLocalNetworking': True})
        if name == 'baseline':
            info.update(CFBundleVersion=str(int(info['CFBundleVersion']) - 1), CFBundleShortVersionString='0.3.99')
        (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
    archive = feed / 'Yukio-test.zip'
    subprocess.run(['ditto', '-c', '-k', '--keepParent', str(a.out/'target/Yukio.app'), str(archive)], check=True)
    sign = [str(a.sign_tool.resolve()), '--ed-key-file', str(key_dir / 'private')]
    signature = subprocess.check_output(sign + ['-p', str(archive)], text=True).strip()
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'Yukio isolated update validation'
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = 'Yukio ' + target_info['CFBundleShortVersionString']
    ET.SubElement(item, 'description').text = '<h2>更新测试</h2><p>Install to test download, replacement, restart and preserved preferences.</p>'
    ET.SubElement(item, 'enclosure', {'url': 'http://127.0.0.1:18744/Yukio-test.zip',
        'length': str(archive.stat().st_size), 'type': 'application/octet-stream',
        f'{{{ns}}}version': target_info['CFBundleVersion'],
        f'{{{ns}}}shortVersionString': target_info['CFBundleShortVersionString'],
        f'{{{ns}}}edSignature': signature})
    ET.ElementTree(rss).write(feed / 'appcast.xml', encoding='utf-8', xml_declaration=True)
    subprocess.run(sign + [str(feed/'appcast.xml')], check=True)
    subprocess.run(sign + ['--verify', str(archive), signature], check=True)
print('Isolated test fixtures prepared. The temporary private key has been deleted.')
print('Feed directory:', feed.resolve())
print('Baseline app:', (a.out/'baseline/Yukio.app').resolve())
