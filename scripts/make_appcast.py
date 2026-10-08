#!/usr/bin/env python3
"""Build a signed Sparkle feed for a versioned release zip. Key stays in Keychain."""
import argparse
import html
import plistlib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

SPARKLE = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
ET.register_namespace('sparkle', SPARKLE)
p = argparse.ArgumentParser()
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--notes', type=Path, required=True)
p.add_argument('--sign-tool', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--url')
a = p.parse_args()
with zipfile.ZipFile(a.archive) as z:
    info = plistlib.loads(z.read('Yukio.app/Contents/Info.plist'))
version = info['CFBundleShortVersionString']
url = a.url or f'https://github.com/leozhang8654/yukio-desktop-pet/releases/download/v{version}/{a.archive.name}'
if not url.startswith('https://'):
    raise SystemExit('Release archives must use HTTPS')
sign = [str(a.sign_tool.resolve()), '--account', 'yukio-desktop-pet']
signature = subprocess.check_output(sign + ['-p', str(a.archive)], text=True).strip()
rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Yukio updates'
item = ET.SubElement(channel, 'item')
ET.SubElement(item, 'title').text = f'Yukio {version}'
ET.SubElement(item, 'description').text = '<pre>' + html.escape(a.notes.read_text()) + '</pre>'
ET.SubElement(item, f'{{{SPARKLE}}}minimumSystemVersion').text = '13.0'
ET.SubElement(item, 'enclosure', {
    'url': url, 'length': str(a.archive.stat().st_size), 'type': 'application/octet-stream',
    f'{{{SPARKLE}}}version': info['CFBundleVersion'],
    f'{{{SPARKLE}}}shortVersionString': version,
    f'{{{SPARKLE}}}edSignature': signature,
})
a.output.parent.mkdir(parents=True, exist_ok=True)
ET.indent(rss)
ET.ElementTree(rss).write(a.output, encoding='utf-8', xml_declaration=True)
subprocess.run(sign + [str(a.output)], check=True)
subprocess.run(sign + ['--verify', str(a.archive), signature], check=True)
print(a.output)
