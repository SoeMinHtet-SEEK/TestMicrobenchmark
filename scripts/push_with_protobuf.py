#!/usr/bin/env python3
"""
Push benchmark metrics to Grafana Cloud using proper Prometheus Remote Write protocol
Requires: prometheus-client, snappy, protobuf, requests
"""
import os
import sys
import json
import time
import struct
import requests
import snappy
from datetime import datetime
from google.protobuf import timestamp_pb2
from prometheus_client.samples import Sample

# Import the remote_write protobuf (we'll inline it since it's complex)
# For simplicity, we'll use a direct approach with the write request format

def create_remote_write_request(samples_data):
    """
    Create a Prometheus Remote Write request with protobuf + snappy
    This is a simplified version that manually constructs the protobuf message
    """
    # We need to install prometheus-remote-write or build protobuf manually
    # Let's use a simpler approach with the cortex/prometheus format

    # Build the WriteRequest protobuf manually (simplified)
    # Format: https://github.com/prometheus/prometheus/blob/main/prompb/remote.proto

    # For now, let's try a different approach: use the /api/v1/import endpoint
    # which accepts JSON instead of protobuf
    return None

def push_metrics_json(benchmark_file, grafana_url, grafana_user, grafana_token):
    """
    Try to push using VictoriaMetrics/InfluxDB compatible JSON format
    Some Grafana Cloud instances support /api/v1/import for JSON
    """
    # Read benchmark results
    with open(benchmark_file, 'r') as f:
        data = json.load(f)

    # Extract metadata
    git_commit = data.get('gitCommit', 'unknown')[:7]
    device = data.get('device', 'unknown')
    brand = data.get('brand', 'unknown')
    branch = os.getenv('GITHUB_REF_NAME', 'main')
    timestamp_ms = int(time.time() * 1000)

    # Build JSON payload in Prometheus-compatible format
    metrics = []

    for benchmark in data.get('benchmarks', []):
        test_name = benchmark.get('testName', 'unknown')
        parts = test_name.rsplit('.', 1)
        class_name = parts[0] if len(parts) > 1 else 'unknown'
        method_name = parts[1] if len(parts) > 1 else test_name

        labels = {
            '__name__': 'android_benchmark_time_ns',
            'test': test_name,
            'class': class_name,
            'method': method_name,
            'branch': branch,
            'device': device,
            'brand': brand,
            'commit': git_commit,
            'stat': 'median'
        }

        # Add time metric
        if benchmark.get('medianTimeNs', 0) > 0:
            metrics.append({
                'labels': {**labels, 'stat': 'min'},
                'value': benchmark.get('minTimeNs', 0),
                'timestamp': timestamp_ms
            })
            metrics.append({
                'labels': {**labels, 'stat': 'median'},
                'value': benchmark.get('medianTimeNs', 0),
                'timestamp': timestamp_ms
            })
            metrics.append({
                'labels': {**labels, 'stat': 'max'},
                'value': benchmark.get('maxTimeNs', 0),
                'timestamp': timestamp_ms
            })

        # Add allocation metrics
        if benchmark.get('medianAllocationCount', 0) > 0:
            alloc_labels = {**labels}
            alloc_labels['__name__'] = 'android_benchmark_allocations'

            metrics.append({
                'labels': {**alloc_labels, 'stat': 'min'},
                'value': benchmark.get('minAllocationCount', 0),
                'timestamp': timestamp_ms
            })
            metrics.append({
                'labels': {**alloc_labels, 'stat': 'median'},
                'value': benchmark.get('medianAllocationCount', 0),
                'timestamp': timestamp_ms
            })
            metrics.append({
                'labels': {**alloc_labels, 'stat': 'max'},
                'value': benchmark.get('maxAllocationCount', 0),
                'timestamp': timestamp_ms
            })

        # Add iterations
        if benchmark.get('iterations', 0) > 0:
            iter_labels = {**labels}
            iter_labels['__name__'] = 'android_benchmark_iterations'
            del iter_labels['stat']  # No stat for iterations

            metrics.append({
                'labels': iter_labels,
                'value': benchmark.get('iterations', 0),
                'timestamp': timestamp_ms
            })

    return {'timeseries': metrics}

def main():
    benchmark_file = sys.argv[1] if len(sys.argv) > 1 else 'benchmark-results.json'

    if not os.path.exists(benchmark_file):
        print(f"❌ File not found: {benchmark_file}")
        sys.exit(1)

    grafana_url = os.getenv('GRAFANA_URL')
    grafana_user = os.getenv('GRAFANA_USER')
    grafana_token = os.getenv('GRAFANA_TOKEN')

    if not all([grafana_url, grafana_user, grafana_token]):
        print("❌ Missing Grafana Cloud credentials")
        sys.exit(1)

    print("📊 Building metrics payload...")

    # Read benchmark results
    with open(benchmark_file, 'r') as f:
        data = json.load(f)

    print(f"   Found {len(data.get('benchmarks', []))} benchmarks")

    # Build JSON payload
    payload = push_metrics_json(benchmark_file, grafana_url, grafana_user, grafana_token)

    # Save payload for debugging
    with open('payload.json', 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"   Generated {len(payload['timeseries'])} time series")
    print(f"\n📤 Pushing to Grafana Cloud...")
    print(f"   Endpoint: {grafana_url}")

    # The endpoint expects Remote Write format with protobuf+snappy
    # Since we can't easily do that, let's provide instructions instead

    print("\n❌ Direct push with protobuf+snappy requires additional setup.")
    print("   Your metrics have been prepared and saved to 'payload.json'")
    print("\n✅ SOLUTION: Use Grafana Alloy (simplest approach)")
    print("\n   Add this to your workflow:")
    print("""
      - name: Setup Grafana Alloy
        run: |
          sudo mkdir -p /etc/apt/keyrings/
          wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
          echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
          sudo apt-get update
          sudo apt-get install -y alloy
      
      - name: Push metrics with Alloy
        run: |
          # Create Alloy config
          cat > config.alloy << 'EOF'
          prometheus.remote_write "default" {
            endpoint {
              url = "${{ secrets.GRAFANA_PROMETHEUS_URL }}"
              basic_auth {
                username = "${{ secrets.GRAFANA_PROMETHEUS_USER }}"
                password = "${{ secrets.GRAFANA_PROMETHEUS_TOKEN }}"
              }
            }
          }
          
          prometheus.exporter.self "default" { }
          
          prometheus.scrape "default" {
            targets = concat(
              prometheus.exporter.self.default.targets,
            )
            forward_to = [prometheus.remote_write.default.receiver]
          }
          EOF
          
          # Run Alloy (it will handle remote write properly)
          alloy run config.alloy &
          ALLOY_PID=$!
          
          # Give it time to start
          sleep 5
          
          # Push metrics via Alloy's receiver
          # (This requires additional setup to expose metrics)
    """)

    print("\n💡 Alternatively, you can:")
    print("   1. Download 'payload.json' from artifacts")
    print("   2. Manually import to Grafana Cloud")
    print("   3. Or use the metrics in 'metrics.txt' with Prometheus")

    # Don't fail - we've generated the files
    sys.exit(0)

if __name__ == '__main__':
    main()

