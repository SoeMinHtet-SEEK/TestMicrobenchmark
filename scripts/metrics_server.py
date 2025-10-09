#!/usr/bin/env python3
"""
Start a simple HTTP server that exposes Prometheus metrics for Alloy to scrape
"""
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Global variable to store metrics in memory
METRICS_DATA = ""

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; version=0.0.4')
                self.end_headers()
                self.wfile.write(METRICS_DATA.encode('utf-8'))
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

def set_metrics(metrics_content):
    """Set the metrics content to serve"""
    global METRICS_DATA
    METRICS_DATA = metrics_content

def start_server(port=9091, metrics_content=""):
    """Start the metrics server"""
    global METRICS_DATA
    METRICS_DATA = metrics_content

    server = HTTPServer(('127.0.0.1', port), MetricsHandler)
    print(f"✅ Metrics server started on http://127.0.0.1:{port}/metrics")

    # Run server in a thread
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    return server

if __name__ == '__main__':
    # When run standalone, read from stdin or a file
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9091

    # Read metrics from stdin
    print("📊 Reading metrics from stdin...")
    metrics = sys.stdin.read()

    if not metrics:
        print("❌ No metrics provided")
        sys.exit(1)

    server = start_server(port, metrics)

    print(f"📊 Serving metrics at http://127.0.0.1:{port}/metrics")
    print("   Press Ctrl+C to stop")

    try:
        # Keep the main thread alive
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        server.shutdown()
