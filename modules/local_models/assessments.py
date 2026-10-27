"""Versioned advisory profiles and scoped measurements; never executable recipes."""
import hashlib
import math
import platform
import sys
import time
from sdk.protocol import PROJECT, digest, read_json

MIB = 1024 ** 2


def identity(item):
    return digest(item)


def context(runtime):
    worker = PROJECT / 'adapters/models/local_embedding_worker.py'
    value = {'device': hashlib.sha256(platform.node().encode()).hexdigest()[:16],
             'os': platform.system(), 'os_release': platform.release(), 'machine': platform.machine(),
             'processor': platform.processor(), 'python': sys.version.split()[0],
             'backend': 'onnx-cpu', 'threads': 2,
             'dependencies': [(x['distribution'], x.get('installed')) for x in runtime.get('dependencies', [])],
             'worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest()}
    return {'id': digest(value), **value}


def merge_sample(previous, memory, workload=None):
    """Ignore missing/invalid counters; a standby zero must never erase calibration."""
    value = dict(previous or {})
    rss = memory.get('rss_bytes') if isinstance(memory, dict) else None
    if type(rss) is not int or not 0 < rss < 1024 ** 5:
        return value
    peak = memory.get('peak_rss_bytes')
    peak = max(rss, peak) if type(peak) is int and 0 < peak < 1024 ** 5 else rss
    value.update(samples=value.get('samples', 0) + 1, rss_bytes=rss,
                 min_rss_bytes=min(value.get('min_rss_bytes', rss), rss),
                 peak_rss_bytes=max(value.get('peak_rss_bytes', 0), peak), updated_at=time.time())
    # Only the CPU adapter is implemented. Zero here describes that backend.
    value['gpu_bytes'] = 0
    if isinstance(workload, dict):
        for key in ('batch', 'max_tokens'):
            n = workload.get(key)
            if type(n) is int and n > 0:
                value[key + '_observed_max'] = max(value.get(key + '_observed_max', 0), n)
    return value


def lower_is_better(value, thresholds):
    return next((5 - i for i, ceiling in enumerate(thresholds) if value <= ceiling), 1)


def assess(item, records, device_context, profiles):
    profile = profiles.get(item['id'])
    if profile and profile.get('manifest_fingerprint') != identity(item):
        profile = None
    profile = profile or {'profile': '尚无经核验的资源规划', 'sources': [], 'official': [], 'notes': [],
                          'languages_count': None, 'expected': {}}
    expected = {k: dict(v) for k, v in profile['expected'].items()}
    if item['files']:
        size = sum(f['bytes'] for f in item['files'])
        expected['disk'] = {'low': size, 'high': size, 'basis': 'pinned_artifacts'}
    current = records.get(device_context['id'], {})
    disk = records.get('artifact', {})
    if disk.get('verified_disk_bytes') is not None:
        expected['disk'] = {'low': disk['verified_disk_bytes'], 'high': disk['verified_disk_bytes'], 'basis': 'measured'}
    if current.get('samples'):
        expected['ram'] = {'low': current['min_rss_bytes'], 'high': math.ceil(current['peak_rss_bytes'] * 1.15),
                           'basis': 'measured_with_15_percent_margin'}
        expected['vram'] = {'low': 0, 'high': 0, 'basis': 'cpu_backend'}
    count = profile.get('languages_count')
    coverage = (5 if count >= 100 else 4 if count >= 30 else 3 if count >= 10 else 2 if count >= 2 else 1) if count else None
    ram = expected.get('ram', {}).get('high')
    benchmark = current.get('benchmark')
    stale_benchmark = benchmark if benchmark and benchmark.get('suite_sha256') != digest(read_json(PROJECT / 'modules/local_models/retrieval-suite.json')) else None
    if stale_benchmark: benchmark = None
    scores = {'resources': lower_is_better(ram / MIB, [512, 1024, 2048, 4096]) if ram is not None else None,
              'multilingual': coverage,
              'speed': lower_is_better(benchmark['latency_ms']['p50'], [20, 50, 150, 500]) if benchmark else None,
              'validation': 3 if benchmark else 2 if current.get('samples') else 1 if disk else 0,
              'retrieval': benchmark['hit_at_1'] * 100 if benchmark else None}
    return {**profile, 'expected': expected, 'scores': scores, 'measured': current,
            'disk_measurement': disk, 'other_contexts': len([k for k in records if k not in ('artifact', device_context['id'])]),
            'context_id': device_context['id'], 'benchmark': benchmark, 'stale_benchmark': bool(stale_benchmark),
            'calibrated': bool(current.get('samples')), 'rules_version': 'resource-scores-v1'}


def profiles():
    return read_json(PROJECT / 'modules/local_models/assessments.json')['models']
