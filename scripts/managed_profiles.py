"""Native host images and routing labels for the managed Homebrew pools."""
import re

from runner_pool import validate_host

TARGET = 'shivammathur/homebrew-extensions'
PROFILES = {
    'macos15': {
        'prefix': 'runner-pool-hb-macos15-', 'arch': 'arm64', 'platform': 'macos-15-arm64',
        'image': 'nscloud-macos-sequoia-stable-arm64-4x7',
        'labels': ('macos-15', 'macos-15-arm64'), 'system': 'macOS',
        'workflow': 'managed-runner.yml', 'limit': 12,
    },
    'macos26': {
        'prefix': 'runner-pool-hb-macos26-', 'arch': 'arm64', 'platform': 'macos-26',
        'image': 'nscloud-macos-tahoe-arm64-4x7',
        'labels': ('macos-26', 'macos-26-arm64'), 'system': 'macOS',
        'workflow': 'managed-runner.yml', 'limit': 12,
    },
    'xcode27': {
        'prefix': 'runner-pool-hb-xcode27-', 'arch': 'arm64', 'platform': 'xcode-27',
        'image': 'nscloud-macos-goldengate-arm64-4x7',
        'labels': ('xcode-27', 'macos-27', 'macos-27-arm64'), 'system': 'macOS',
        'workflow': 'managed-runner.yml', 'limit': 12,
    },
}


def identify(name):
    for key, profile in PROFILES.items():
        match = re.fullmatch(profile['prefix'] + r's([1-9][0-9]?)-[0-9]{8}-[0-9]{6}-[a-f0-9]{6}', name)
        if match and int(match[1]) <= profile['limit']:
            return key, int(match[1])
    return None


def labels(key):
    profile = PROFILES[key]
    return ['self-hosted', profile['system'], 'X64' if profile['arch'] == 'x64' else 'ARM64', *profile['labels']]


def validate(key, system, machine, version):
    profile = PROFILES[key]
    validate_host(profile['platform'], profile['arch'], system, machine, version)
