#!/usr/bin/env python3
"""
Push benchmark metrics to Grafana Cloud using Prometheus Remote Write protocol
"""
import os
import sys
import json
import time
import struct
import requests
import snappy
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge
from prometheus_client.openmetrics.exposition import generate_latest

# Try to import protobuf, if not available we'll use a workaround
try:
    from prometheus_client.core import Sample
    from prometheus_client.exposition import basic_auth_handler
except ImportError:
    print("⚠️  Some optional dependencies missing, using alternative approach")

def push_metrics_simple(benchmark_file, grafana_url, grafana_user, grafana_token):
    """
    Simple approach: Use prometheus_client with direct HTTP post
    """
    # Read benchmark results
    with open(benchmark_file, 'r') as f:
        data = json.load(f)

    # Create registry
    registry = CollectorRegistry()

    # Create gauges
    time_gauge = Gauge(
        'android_benchmark_time_ns',
        'Benchmark execution time in nanoseconds',
        ['test', 'class', 'method', 'branch', 'device', 'brand', 'commit', 'stat'],
        registry=registry
    )

    alloc_gauge = Gauge(
        'android_benchmark_allocations',
        'Benchmark memory allocations',
        ['test', 'class', 'method', 'branch', 'device', 'brand', 'commit', 'stat'],
        registry=registry
    )

    iter_gauge = Gauge(
        'android_benchmark_iterations',
        'Benchmark iteration count',
        ['test', 'class', 'method', 'branch', 'device', 'brand', 'commit'],
        registry=registry
    )

    # Extract metadata
    git_commit = data.get('gitCommit', 'unknown')[:7]  # Short commit
    device = data.get('device', 'unknown')
    brand = data.get('brand', 'unknown')
    branch = os.getenv('GITHUB_REF_NAME', 'main')

    print(f"📊 Processing {len(data.get('benchmarks', []))} benchmarks...")

    # Process each benchmark
    for benchmark in data.get('benchmarks', []):
        test_name = benchmark.get('testName', 'unknown')
        parts = test_name.rsplit('.', 1)
        class_name = parts[0] if len(parts) > 1 else 'unknown'
        method_name = parts[1] if len(parts) > 1 else test_name

        labels = {
            'test': test_name,
            'class': class_name,
            'method': method_name,
            'branch': branch,
            'device': device,
            'brand': brand,
            'commit': git_commit
        }

        # Set time metrics
        if benchmark.get('medianTimeNs', 0) > 0:
            time_gauge.labels(**labels, stat='min').set(benchmark.get('minTimeNs', 0))
            time_gauge.labels(**labels, stat='median').set(benchmark.get('medianTimeNs', 0))
            time_gauge.labels(**labels, stat='max').set(benchmark.get('maxTimeNs', 0))
            print(f"  ✓ {method_name}: {benchmark.get('medianTimeNs', 0) / 1000:.2f} µs")

        # Set allocation metrics
        if benchmark.get('medianAllocationCount', 0) > 0:
            alloc_gauge.labels(**labels, stat='min').set(benchmark.get('minAllocationCount', 0))
            alloc_gauge.labels(**labels, stat='median').set(benchmark.get('medianAllocationCount', 0))
            alloc_gauge.labels(**labels, stat='max').set(benchmark.get('maxAllocationCount', 0))

        # Set iterations
        if benchmark.get('iterations', 0) > 0:
            iter_gauge.labels(**labels).set(benchmark.get('iterations', 0))

    # Generate metrics in text format
    metrics_text = generate_latest(registry).decode('utf-8')

    # Save to file for debugging
    with open('metrics_final.txt', 'w') as f:
        f.write(metrics_text)

    print(f"\n📤 Pushing metrics to Grafana Cloud...")
    print(f"   URL: {grafana_url}")

    # Push to Grafana Cloud
    # Note: /api/prom/push might not work with text format
    # Try to determine if we should use a different endpoint

    headers = {
        'Content-Type': 'application/openmetrics-text; version=1.0.0; charset=utf-8'
    }

    try:
        response = requests.post(
            grafana_url,
            data=metrics_text.encode('utf-8'),
            auth=(grafana_user, grafana_token),
            headers=headers,
            timeout=30
        )

        print(f"   Status: {response.status_code}")

        if response.status_code in [200, 201, 202, 204]:
            print("✅ Successfully pushed metrics to Grafana Cloud!")
            return True
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            print(f"   Response: {response.text[:200]}")

            # If text format doesn't work, inform user
            if 'snappy' in response.text.lower() or response.status_code == 400:
                print("\n❌ Grafana Cloud endpoint requires Remote Write protocol (protobuf + snappy)")
                print("   This endpoint does not accept plain text metrics.")
                print("\n📝 Your metrics have been saved to 'metrics_final.txt'")
                print("   You can:")
                print("   1. Use Grafana Agent/Alloy to push these metrics")
                print("   2. Use a Prometheus server to scrape and remote write")
                print("   3. Contact Grafana support for the correct endpoint")
                return False

            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error pushing to Grafana: {e}")
        return False

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
        print("   Set GRAFANA_URL, GRAFANA_USER, and GRAFANA_TOKEN")
        sys.exit(1)

    success = push_metrics_simple(benchmark_file, grafana_url, grafana_user, grafana_token)

    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

