#!/usr/bin/env python3
"""
Start a simple HTTP server that exposes Prometheus metrics for Alloy to scrape
"""
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            # Read the metrics file
            try:
                with open('metrics.txt', 'r') as f:
                    metrics = f.read()

                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; version=0.0.4')
                self.end_headers()
                self.wfile.write(metrics.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass

def start_server(port=9091):
    """Start the metrics server"""
    server = HTTPServer(('127.0.0.1', port), MetricsHandler)
    print(f"✅ Metrics server started on http://127.0.0.1:{port}/metrics")

    # Run server in a thread
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    return server

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9091

    if not os.path.exists('metrics.txt'):
        print("❌ metrics.txt not found")
        sys.exit(1)

    server = start_server(port)

    print(f"📊 Serving metrics at http://127.0.0.1:{port}/metrics")
    print("   Press Ctrl+C to stop")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        server.shutdown()

