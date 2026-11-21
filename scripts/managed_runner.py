"""Serve exactly one Homebrew job, then destroy the disposable native host."""
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time

from managed_profiles import PROFILES, TARGET, identify, labels, validate
from runner_pool import child_environment, download_runner, start_runner, stop

PREFIX = PROFILES['macos15']['prefix']
MACOS_LABELS = PROFILES['macos15']['labels']
# Avoid keeping an unused VM when another runner wins the queued job.
ACCEPT_SECONDS = 10 * 60
MAX_SECONDS = 340 * 60


def validate_namespace_shape(cpu_count, memory_bytes):
    # Accept either decimal GB or GiB reporting for the requested 4x7 shape.
    if cpu_count != 4 or not 7_000_000_000 <= memory_bytes <= 7 * 1024 ** 3:
        raise ValueError('Expected a Namespace 4-vCPU/7-GB macOS host')


def serve_job(directory, env, log, accept_seconds=ACCEPT_SECONDS, max_seconds=MAX_SECONDS):
    started = time.monotonic()
    process = None
    try:
        previous = set((directory / '_diag').glob('Worker_*.log'))
        process = start_runner(directory, None, env, log)
        assigned = False
        while True:
            result = process.poll()
            assigned = assigned or bool(set((directory / '_diag').glob('Worker_*.log')) - previous)
            if result is not None:
                if result != 0 or not assigned:
                    raise RuntimeError('Runner listener exited without completing a job')
                print('Completed one job; retiring host.', flush=True)
                return 1
            elapsed = time.monotonic() - started
            if not assigned and elapsed >= accept_seconds:
                print('No job assigned within ten minutes; retiring unused host.', flush=True)
                return 0
            if elapsed >= max_seconds:
                raise TimeoutError('Host execution deadline reached')
            time.sleep(2)
    finally:
        stop(process)


def configure_runner(directory, key, name, token, env, log):
    subprocess.run([
        './config.sh', '--unattended', '--ephemeral', '--url', f'https://github.com/{TARGET}',
        '--token', token, '--name', name, '--work', '_work',
        '--no-default-labels', '--labels', ','.join(labels(key)),
    ], cwd=directory, env=env, stdout=log, stderr=log, timeout=120, check=True)


def serve():
    os.umask(0o077)
    token = os.environ.pop('RUNNER_REGISTRATION_TOKEN')
    name = os.environ.pop('POOL')
    identity = identify(name)
    if identity is None:
        raise ValueError('Invalid managed runner name')
    key, _ = identity
    profile = PROFILES[key]
    if os.environ.pop('POOL_ARCH', profile['arch']) != profile['arch']:
        raise ValueError('Runner name does not match the selected architecture')
    if not re.fullmatch(r'[A-Za-z0-9_]+', token):
        raise ValueError('Invalid registration token')
    system = platform.system()
    version = platform.freedesktop_os_release()['VERSION_ID'] if system == 'Linux' else platform.mac_ver()[0]
    validate(key, system, platform.machine(), version)
    if system == 'Darwin':
        cpus = int(subprocess.check_output(['sysctl', '-n', 'hw.ncpu'], text=True))
        memory = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True))
        validate_namespace_shape(cpus, memory)
        xcode = subprocess.check_output(['xcodebuild', '-version'], text=True).strip()
        if key == 'xcode27' and not re.match(r'Xcode 27(?:\.|\s)', xcode):
            raise ValueError('Expected Xcode 27 on the macOS 27 host')
        print(f'Host verified: macOS {version}, {platform.machine()}, '
              f'{cpus} vCPUs, {memory} bytes RAM; {xcode}.', flush=True)
    env = child_environment(os.environ)
    directory = Path(tempfile.mkdtemp(prefix='managed-runner-', dir=os.environ['RUNNER_TEMP']))

    def interrupted(signum, frame):
        raise InterruptedError('Host workflow interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        download_runner(directory, profile['arch'], profile['platform'])
        print(f'Pinned {key} runner verified.', flush=True)
        with (directory / 'host.log').open('wb') as log:
            configure_runner(directory, key, name, token, env, log)
            token = ''
            print(f'Registered ephemeral {key} runner for one job.', flush=True)
            serve_job(directory, env, log)
    finally:
        subprocess.run(['sudo', 'rm', '-rf', '--', str(directory)], check=False)


if __name__ == '__main__':
    try:
        serve()
    except BaseException as error:
        print(f'::error::Managed runner failed ({type(error).__name__}).', file=sys.stderr)
        sys.exit(1)
