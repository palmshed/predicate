#!/usr/bin/env python3
"""Development server that injects the design inspector into HTML pages.

Usage:
    python3 serve.py

Serves on http://localhost:8000. Only intended for local development.
Production files are never modified.
"""

import http.server
import os
import sys

PORT = 8000
DIR = os.path.dirname(os.path.abspath(__file__))

class DevServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.translate_path(self.path)
        if path.endswith('.html') and os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            script = '<script src="./design-mode.js"></script>'
            content = content.replace('</body>', script + '\n  </body>')
            data = content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            super().do_GET()

if __name__ == '__main__':
    os.chdir(DIR)
    server = http.server.HTTPServer(('localhost', PORT), DevServer)
    print(f'-> http://localhost:{PORT}')
    print('  Design inspector injected into HTML pages.')
    print('  Production files are untouched.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
        server.server_close()
