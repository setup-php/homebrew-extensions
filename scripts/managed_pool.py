"""Launch single-job Namespace macOS hosts only for uncovered queued jobs."""
import collections
import concurrent.futures
import datetime
import json
import os
import secrets
import subprocess

from managed_profiles import PROFILES, TARGET, identify, labels

HOST = 'setup-php/homebrew-extensions'
MAX_HOSTS = 12
BRANCH = 'feature/ephemeral-runner-pool'


def gh(path, method='GET', data=None):
    command = ['gh', 'api', path, '--method', method]
    if data is not None:
        command += ['--input', '-']
    response = subprocess.run(command, input=json.dumps(data).encode() if data is not None else None,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if response.returncode:
        raise RuntimeError('GitHub API operation failed: ' + method + ' ' + path.split('/actions/')[0])
    return json.loads(response.stdout) if response.stdout else None


def pages(path, key):
    result = []
    for page in range(1, 100):
        response = gh(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        result.extend(response[key])
        if len(response[key]) < 100:
            return result
    raise RuntimeError('Inventory exceeded pagination limit')


def pool_runs(runs):
    return {name: run for run in runs
            if run['display_title'].startswith('Managed runner ')
            and identify(name := run['display_title'].removeprefix('Managed runner '))}


def active_pools(runs):
    return {name: run for name, run in pool_runs(runs).items() if run['status'] != 'completed'}


def target_jobs():
    # Matrix jobs can be queued inside an in-progress workflow. Runs waiting
    # for approval or workflow concurrency are not ready to consume a host.
    runs = {}
    for status in ('queued', 'in_progress'):
        for run in pages(f'repos/{TARGET}/actions/runs?status={status}', 'workflow_runs'):
            runs[run['id']] = run
    jobs = {}
    for ident in runs:
        for job in pages(f'repos/{TARGET}/actions/runs/{ident}/jobs?filter=latest', 'jobs'):
            jobs[job['id']] = job
    return list(jobs.values())


def matching_profile(job):
    requested = {label.lower() for label in job.get('labels', [])}
    if not requested:
        return None
    candidates = [key for key in PROFILES if requested <= {label.lower() for label in labels(key)}]
    # Generic macOS labels are ambiguous; never invent a deployment baseline.
    return candidates[0] if len(candidates) == 1 else None


def plan_launches(protected, runners, jobs, capacity):
    protected = set(protected)
    registered = {runner['name']: runner for runner in runners}
    consumed = {job.get('runner_name') for job in jobs if job['status'] != 'queued'}
    waiting = []
    occupied = collections.defaultdict(set)
    for name in sorted(protected):
        key, number = identify(name)
        occupied[key].add(number)
        # Busy single-job hosts cannot take another job. Booting, reserved and
        # online-idle hosts can each cover one queued job without another VM.
        if name not in consumed and not registered.get(name, {}).get('busy', False):
            waiting.append({label.lower() for label in labels(key)})
    # Existing permanent idle runners may pick up a job before our next poll.
    for runner in runners:
        if not identify(runner['name']) and runner['status'] == 'online' and not runner['busy']:
            waiting.append({label['name'].lower() for label in runner['labels']})

    queued = {key: 0 for key in PROFILES}
    covered = dict(queued)
    deferred = dict(queued)
    planned = []
    budget = max(0, capacity - len(protected))
    unique = {job['id']: job for job in jobs}
    for job in sorted(unique.values(), key=lambda job: (job.get('created_at') or '', job['id'])):
        if job['status'] != 'queued' or job.get('runner_name'):
            continue
        key = matching_profile(job)
        if key is None:
            continue
        queued[key] += 1
        requested = {label.lower() for label in job['labels']}
        match = next((index for index, available in enumerate(waiting) if requested <= available), None)
        if match is not None:
            waiting.pop(match)
            covered[key] += 1
            continue
        if not budget:
            deferred[key] += 1
            continue
        number = next(slot for slot in range(1, MAX_HOSTS + 1) if slot not in occupied[key])
        occupied[key].add(number)
        planned.append((key, number))
        budget -= 1
    return planned, queued, covered, deferred


def create_environment(name):
    gh(f'repos/{HOST}/environments/{name}', 'PUT', {
        'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True},
    })
    gh(f'repos/{HOST}/environments/{name}/deployment-branch-policies', 'POST',
       {'name': BRANCH, 'type': 'branch'})


def refresh_registration(name):
    registration = gh(f'repos/{TARGET}/actions/runners/registration-token', 'POST')
    subprocess.run(['gh', 'secret', 'set', 'RUNNER_REGISTRATION_TOKEN', '-R', HOST, '--env', name],
                   input=registration['token'].encode(), stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True)
    del registration


def launch(number, now, key):
    profile = PROFILES[key]
    pool = profile['prefix'] + f's{number}-' + now.strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3)
    create_environment(pool)
    refresh_registration(pool)
    gh(f'repos/{HOST}/actions/workflows/{profile["workflow"]}/dispatches', 'POST',
       {'ref': BRANCH, 'inputs': {'pool': pool, 'image': profile['image']}})
    print(f'Dispatched {key} slot {number}: {pool}', flush=True)


def maintain():
    capacity = int(os.environ.get('HOST_CAPACITY', str(MAX_HOSTS)))
    if not 0 <= capacity <= MAX_HOSTS:
        raise ValueError('HOST_CAPACITY must be between zero and twelve')
    dry_run = os.environ.get('DRY_RUN', 'false').lower() == 'true'
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    runs = pages(f'repos/{HOST}/actions/runs?branch={BRANCH}&created=>={since}', 'workflow_runs')
    known = pool_runs(runs)
    active = active_pools(runs)
    runners = pages(f'repos/{TARGET}/actions/runners', 'runners')
    registered = {runner['name'] for runner in runners}
    environments = pages(f'repos/{HOST}/environments', 'environments')
    jobs = target_jobs()
    protected = set(active)
    for runner in runners:
        name = runner['name']
        if identify(name) is None or name in active:
            continue
        finished = name in known and known[name]['status'] == 'completed'
        if runner['busy'] or (runner['status'] != 'offline' and not finished):
            protected.add(name)
            continue
        if not dry_run:
            gh(f'repos/{TARGET}/actions/runners/{runner["id"]}', 'DELETE')
            print(f'Removed stopped runner {name}', flush=True)
    for environment in environments:
        name = environment['name']
        if identify(name) is None or name in protected:
            continue
        age = now - datetime.datetime.fromisoformat(environment['created_at'].replace('Z', '+00:00'))
        if name not in known and age < datetime.timedelta(minutes=30):
            # Reserve a slot for dispatch visibility delays or partial setup.
            protected.add(name)
            continue
        # A completed single-job host must release its slot immediately, even
        # if its environment was created less than thirty minutes ago.
        if not dry_run:
            gh(f'repos/{HOST}/environments/{name}', 'DELETE')
            print(f'Removed finished environment {name}', flush=True)
    consumed = {job.get('runner_name') for job in jobs if job['status'] != 'queued'}
    for name, run in active.items():
        age = now - datetime.datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        if name not in registered and name not in consumed and age > datetime.timedelta(minutes=45):
            if not dry_run:
                gh(f"repos/{HOST}/actions/runs/{run['id']}/cancel", 'POST')
                print(f'Cancelled stale queued host {name}', flush=True)
    planned, queued, covered, deferred = plan_launches(protected, runners, jobs, capacity)
    print(json.dumps({'queued_jobs': queued, 'covered_by_existing_hosts': covered,
                      'active_hosts': len(active), 'reserved_hosts': len(protected),
                      'host_capacity': capacity, 'launching_slots': planned,
                      'capacity_deferred': deferred, 'dry_run': dry_run}), flush=True)
    if dry_run or not planned:
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = [executor.submit(launch, number, now, key) for key, number in planned]
        errors = []
        for result in results:
            try:
                result.result()
            except Exception as error:
                errors.append(type(error).__name__)
        if errors:
            raise RuntimeError('Runner launch failures: ' + ', '.join(errors))


if __name__ == '__main__':
    maintain()
