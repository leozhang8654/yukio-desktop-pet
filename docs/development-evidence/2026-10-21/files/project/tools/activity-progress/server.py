#!/usr/bin/env python3
"""Loopback-only, read-only project progress site. Never serves the repository."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8')}


def read_json(path):
    with open(path, 'rb') as stream:
        data = stream.read((1 << 20) + 1)
    if len(data) > 1 << 20:
        raise ValueError('Status file too large')
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError('Status must be an object')
    return value


def snapshot(progress, runtime):
    project = read_json(progress)
    collector = None
    if runtime:
        try:
            data = read_json(runtime)
            # Only aggregate status is exposed. No source paths, IDs, bodies or raw errors.
            fields = ('state', 'updated_at', 'started_at', 'discovered_files', 'tracked_files',
                      'pending_files', 'error_files', 'events_saved_this_run', 'database_bytes',
                      'max_database_bytes', 'scan_complete', 'last_scan_at', 'source_available',
                      'issue', 'mode', 'backend')
            collector = {k: data[k] for k in fields if k in data}
        except (OSError, ValueError):
            collector = {'state': 'unavailable'}
    return dict(project=project, collector=collector, served_at=datetime.now(timezone.utc).isoformat())


def create_server(port, progress, runtime=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            allowed = {'127.0.0.1:%d' % self.server.server_port, 'localhost:%d' % self.server.server_port}
            if self.headers.get('Host') not in allowed:
                return self.reply(403, b'Local access only', 'text/plain')
            origin = self.headers.get('Origin')
            if origin and origin not in {'http://' + host for host in allowed}:
                return self.reply(403, b'Local access only', 'text/plain')
            path = urlsplit(self.path).path
            if path == '/api/status':
                try:
                    value = snapshot(progress, runtime)
                    return self.reply(200, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')
                except (OSError, ValueError):
                    return self.reply(503, b'{"error":"Progress temporarily unavailable"}', 'application/json')
            if path in ASSETS:
                name, content_type = ASSETS[path]
                return self.reply(200, (ROOT / 'dist' / name).read_bytes(), content_type)
            return self.reply(404, b'Not found', 'text/plain')

        def reply(self, code, data, content_type):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--progress', type=Path, default=ROOT / 'progress.json')
    parser.add_argument('--runtime', type=Path)
    args = parser.parse_args()
    server = create_server(args.port, args.progress, args.runtime)
    print('Yukio progress: http://127.0.0.1:%d' % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
