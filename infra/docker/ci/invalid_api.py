"""Synthetic HTTP responses for the isolated n8n diagnostic workflow."""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class InvalidResponse(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{" if self.path.endswith("/health") else b"{}")


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ["CI_FIXTURE_PORT"])), InvalidResponse).serve_forever()
