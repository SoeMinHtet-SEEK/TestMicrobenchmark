#!/usr/bin/env python3
"""
Push Android benchmark results to Grafana Cloud (Prometheus)
Directly processes raw benchmark output files from Android Benchmark library
"""
import json
import sys
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

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

def get_git_commit():
    """Get current git commit hash (short)"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short=7', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return os.getenv('GITHUB_SHA', 'unknown')[:7]

def find_benchmark_files(output_dir):
    """Find all benchmark JSON files in the output directory"""
    benchmark_files = []
    output_path = Path(output_dir)

    if not output_path.exists():
        print(f"❌ Output directory not found: {output_dir}")
        return benchmark_files

    # Walk through all subdirectories to find benchmarkData JSON files
    for json_file in output_path.rglob("*benchmarkData*.json"):
        if json_file.is_file():
            benchmark_files.append(json_file)

    return benchmark_files

def parse_raw_benchmark_json(json_file):
    """Parse raw Android Benchmark JSON output"""
    with open(json_file, 'r') as f:
        data = json.load(f)

    results = []

    # Extract device info from context
    context = data.get('context', {})
    build_info = context.get('build', {})
    device = build_info.get('model', 'unknown')
    brand = build_info.get('brand', 'unknown')

    # Process each benchmark
    benchmarks = data.get('benchmarks', [])

    for benchmark in benchmarks:
        test_name = benchmark.get('name', 'unknown')
        class_name = benchmark.get('className', 'unknown')
        full_test_name = f"{class_name}.{test_name}"

        metrics = benchmark.get('metrics', {})

        # Time metrics
        time_ns = metrics.get('timeNs', {})
        min_time = int(time_ns.get('minimum', 0))
        median_time = int(time_ns.get('median', 0))
        max_time = int(time_ns.get('maximum', 0))

        # Allocation metrics
        alloc_count = metrics.get('allocationCount', {})
        min_alloc = int(alloc_count.get('minimum', 0))
        median_alloc = int(alloc_count.get('median', 0))
        max_alloc = int(alloc_count.get('maximum', 0))

        # Calculate iterations from runs if available
        time_runs = time_ns.get('runs', [])
        iterations = len(time_runs)

        results.append({
            'testName': full_test_name,
            'className': class_name,
            'methodName': test_name,
            'minTimeNs': min_time,
            'medianTimeNs': median_time,
            'maxTimeNs': max_time,
            'minAllocationCount': min_alloc,
            'medianAllocationCount': median_alloc,
            'maxAllocationCount': max_alloc,
            'iterations': iterations,
            'device': device,
            'brand': brand
        })

    return results

def generate_prometheus_metrics(benchmark_results, git_commit, branch):
    """Generate Prometheus format metrics"""
    metrics = []

    for result in benchmark_results:
        test_name = result['testName']
        class_name = result['className']
        method_name = result['methodName']
        device = result['device']
        brand = result['brand']

        # Escape quotes in labels
        test_name_escaped = test_name.replace('"', '\\"')
        class_name_escaped = class_name.replace('"', '\\"')
        method_name_escaped = method_name.replace('"', '\\"')

        # Common labels for all metrics
        labels = f'test="{test_name_escaped}",class="{class_name_escaped}",method="{method_name_escaped}",branch="{branch}",device="{device}",brand="{brand}",commit="{git_commit}"'

        # Time metrics (in nanoseconds)
        if result['medianTimeNs'] > 0:
            metrics.append(f'android_benchmark_time_ns{{{labels},stat="min"}} {result["minTimeNs"]}')
            metrics.append(f'android_benchmark_time_ns{{{labels},stat="median"}} {result["medianTimeNs"]}')
            metrics.append(f'android_benchmark_time_ns{{{labels},stat="max"}} {result["maxTimeNs"]}')

        # Allocation metrics
        if result['medianAllocationCount'] > 0:
            metrics.append(f'android_benchmark_allocations{{{labels},stat="min"}} {result["minAllocationCount"]}')
            metrics.append(f'android_benchmark_allocations{{{labels},stat="median"}} {result["medianAllocationCount"]}')
            metrics.append(f'android_benchmark_allocations{{{labels},stat="max"}} {result["maxAllocationCount"]}')

        # Iterations
        if result['iterations'] > 0:
            metrics.append(f'android_benchmark_iterations{{{labels}}} {result["iterations"]}')

    return metrics

def main():
    if len(sys.argv) != 2:
        print("Usage: push_to_grafana.py <benchmark-output-directory>")
        print("Example: push_to_grafana.py benchmark/build/outputs/connected_android_test_additional_output")
        sys.exit(1)

    output_dir = sys.argv[1]

    print(f"🔍 Looking for benchmark results in: {output_dir}", file=sys.stderr)

    # Find all benchmark JSON files
    benchmark_files = find_benchmark_files(output_dir)

    if not benchmark_files:
        print("⚠️  No benchmark files found", file=sys.stderr)
        sys.exit(0)

    print(f"📄 Found {len(benchmark_files)} benchmark file(s)", file=sys.stderr)

    # Get metadata
    git_commit = get_git_commit()
    branch = get_git_branch()

    # Parse all benchmark files
    all_results = []
    for json_file in benchmark_files:
        print(f"  📄 Processing: {json_file.name}", file=sys.stderr)
        try:
            results = parse_raw_benchmark_json(json_file)
            all_results.extend(results)
            print(f"    ✅ Extracted {len(results)} benchmark(s)", file=sys.stderr)
        except Exception as e:
            print(f"    ⚠️  Error processing {json_file.name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

    if not all_results:
        print("⚠️  No benchmark results extracted", file=sys.stderr)
        sys.exit(0)

    print(f"\n📊 Total benchmarks extracted: {len(all_results)}", file=sys.stderr)

    # Generate Prometheus format metrics
    print(f"\n📈 Generating Prometheus metrics...", file=sys.stderr)
    prometheus_metrics = generate_prometheus_metrics(all_results, git_commit, branch)

    print(f"✅ Generated {len(prometheus_metrics)} metrics", file=sys.stderr)

    # Display sample metrics to stderr
    print("\n📊 Sample Prometheus metrics:", file=sys.stderr)
    for metric in prometheus_metrics[:5]:
        print(f"  {metric}", file=sys.stderr)
    if len(prometheus_metrics) > 5:
        print(f"  ... and {len(prometheus_metrics) - 5} more", file=sys.stderr)

    print("\n✅ Metrics generation complete!", file=sys.stderr)

    # Output metrics to stdout for piping
    print('\n'.join(prometheus_metrics))

if __name__ == "__main__":
    main()