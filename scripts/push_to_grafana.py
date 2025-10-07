#!/usr/bin/env python3
"""
Push Android benchmark results to Grafana Cloud (Prometheus)
"""
import json
import sys
import os
import subprocess
import time
from datetime import datetime

def get_git_branch():
    """Get current git branch name"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return os.getenv('GITHUB_REF_NAME', 'unknown')

def parse_benchmark_json(json_file):
    """Parse benchmark JSON and convert to Prometheus format"""

    with open(json_file, 'r') as f:
        data = json.load(f)

    # Get metadata
    git_commit = data.get('gitCommit', 'unknown')[:7]  # Short commit
    device = data.get('device', 'unknown')
    brand = data.get('brand', 'unknown')
    branch = get_git_branch()

    metrics = []

    # Process each benchmark
    benchmarks = data.get('benchmarks', [])

    for benchmark in benchmarks:
        test_name = benchmark.get('testName', 'unknown')

        # Split test name into class and method if possible
        if '.' in test_name:
            parts = test_name.rsplit('.', 1)
            class_name = parts[0] if len(parts) > 1 else 'unknown'
            method_name = parts[1] if len(parts) > 1 else test_name
        else:
            class_name = 'unknown'
            method_name = test_name

        # Escape quotes in labels
        test_name_escaped = test_name.replace('"', '\\"')
        class_name_escaped = class_name.replace('"', '\\"')
        method_name_escaped = method_name.replace('"', '\\"')

        # Common labels for all metrics
        labels = f'test="{test_name_escaped}",class="{class_name_escaped}",method="{method_name_escaped}",branch="{branch}",device="{device}",brand="{brand}",commit="{git_commit}"'

        # Time metrics (in nanoseconds)
        min_time = benchmark.get('minTimeNs', 0)
        median_time = benchmark.get('medianTimeNs', 0)
        max_time = benchmark.get('maxTimeNs', 0)

        if median_time > 0:
            # No timestamp - Prometheus will add it when scraping
            metrics.append(f'android_benchmark_time_ns{{{labels},stat="min"}} {min_time}')
            metrics.append(f'android_benchmark_time_ns{{{labels},stat="median"}} {median_time}')
            metrics.append(f'android_benchmark_time_ns{{{labels},stat="max"}} {max_time}')

        # Allocation metrics
        min_alloc = benchmark.get('minAllocationCount', 0)
        median_alloc = benchmark.get('medianAllocationCount', 0)
        max_alloc = benchmark.get('maxAllocationCount', 0)

        if median_alloc > 0:
            metrics.append(f'android_benchmark_allocations{{{labels},stat="min"}} {min_alloc}')
            metrics.append(f'android_benchmark_allocations{{{labels},stat="median"}} {median_alloc}')
            metrics.append(f'android_benchmark_allocations{{{labels},stat="max"}} {max_alloc}')

        # Iterations
        iterations = benchmark.get('iterations', 0)
        if iterations > 0:
            metrics.append(f'android_benchmark_iterations{{{labels}}} {iterations}')

    return metrics

def push_to_grafana_influx_format(json_file):
    """
    Alternative approach: Convert to InfluxDB line protocol format
    which Grafana Cloud can accept via their InfluxDB-compatible endpoint
    """
    with open(json_file, 'r') as f:
        data = json.load(f)

    git_commit = data.get('gitCommit', 'unknown')
    device = data.get('device', 'unknown')
    brand = data.get('brand', 'unknown')
    branch = get_git_branch()

    # Get current timestamp in nanoseconds
    timestamp_ns = int(time.time() * 1_000_000_000)

    lines = []
    benchmarks = data.get('benchmarks', [])

    for benchmark in benchmarks:
        test_name = benchmark.get('testName', 'unknown')
        parts = test_name.rsplit('.', 1)
        class_name = parts[0] if len(parts) > 1 else 'unknown'
        method_name = parts[1] if len(parts) > 1 else test_name

        # InfluxDB line protocol format
        # measurement,tag1=value1,tag2=value2 field1=value1,field2=value2 timestamp
        tags = f'test={test_name},class={class_name},method={method_name},branch={branch},device={device},brand={brand},commit={git_commit}'

        median_time = benchmark.get('medianTimeNs', 0)
        median_alloc = benchmark.get('medianAllocationCount', 0)
        iterations = benchmark.get('iterations', 0)

        if median_time > 0:
            lines.append(f'android_benchmark,{tags} time_ns={median_time}i,allocations={median_alloc}i,iterations={iterations}i {timestamp_ns}')

    return lines

def main():
    if len(sys.argv) != 2:
        print("Usage: push_to_grafana.py <benchmark-results.json>")
        sys.exit(1)

    json_file = sys.argv[1]

    if not os.path.exists(json_file):
        print(f"❌ Error: File not found: {json_file}")
        sys.exit(1)

    print(f"📊 Parsing benchmark results from: {json_file}")

    try:
        metrics = parse_benchmark_json(json_file)

        if not metrics:
            print("⚠️  No metrics found in benchmark results")
            sys.exit(0)

        print(f"✅ Generated {len(metrics)} metrics")
        print("\n📈 Sample metrics:")
        for metric in metrics[:5]:
            print(f"  {metric}")

        if len(metrics) > 5:
            print(f"  ... and {len(metrics) - 5} more")

        # Write Prometheus format to file for curl to use
        with open('metrics.txt', 'w') as f:
            f.write('\n'.join(metrics))

        print(f"\n✅ Metrics written to metrics.txt (Prometheus format)")

        # Also generate InfluxDB format as alternative
        influx_lines = push_to_grafana_influx_format(json_file)
        with open('metrics_influx.txt', 'w') as f:
            f.write('\n'.join(influx_lines))

        print(f"✅ Metrics written to metrics_influx.txt (InfluxDB format)")

    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()