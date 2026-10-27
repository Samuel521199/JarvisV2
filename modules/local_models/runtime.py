"""Metadata-only dependency check; the Host never imports inference libraries."""
from importlib import metadata
from sdk.protocol import PROJECT, read_json


def status():
    manifest = read_json(PROJECT / 'modules/local_models/runtime.json')
    dependencies = []
    for item in manifest['dependencies']:
        try:
            installed = metadata.version(item['distribution'])
        except metadata.PackageNotFoundError:
            installed = None
        dependencies.append({**item, 'installed': installed, 'ready': installed == item['version']})
    return {'id': manifest['runtime'], 'ready': all(x['ready'] for x in dependencies),
            'dependencies': dependencies, 'installation': manifest['install_policy'],
            'portability': manifest['portability']}
