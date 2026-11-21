import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import managed_pool as controller
import managed_runner as runner
from managed_profiles import PROFILES, labels


def name(key='macos15', slot=1):
    return PROFILES[key]['prefix'] + f's{slot}-20261118-120000-aabbcc'


def job(ident, key='macos15', status='queued', runner_name=''):
    return {'id': ident, 'labels': list(PROFILES[key]['labels']),
            'status': status, 'runner_name': runner_name}


def registration(key='macos15', slot=1, busy=False, status='online'):
    return {'id': slot, 'name': name(key, slot), 'status': status, 'busy': busy,
            'labels': [{'name': label} for label in labels(key)]}


class DemandPoolTests(unittest.TestCase):
    def test_empty_queue_never_launches_a_warm_pool(self):
        planned, queued, covered, deferred = controller.plan_launches(set(), [], [], 12)
        self.assertEqual(planned, [])
        self.assertEqual(sum(queued.values()) + sum(covered.values()) + sum(deferred.values()), 0)

    def test_all_twelve_slots_can_serve_one_os_without_fixed_split(self):
        planned, queued, _, deferred = controller.plan_launches(set(), [], [job(n, 'macos26') for n in range(20)], 12)
        self.assertEqual(planned, [('macos26', n) for n in range(1, 13)])
        self.assertEqual(queued['macos26'], 20)
        self.assertEqual(deferred['macos26'], 8)

    def test_queue_order_and_exact_job_labels_select_native_images(self):
        jobs = [job(3, 'xcode27'), job(1, 'macos15'), job(2, 'macos26')]
        self.assertEqual(controller.plan_launches(set(), [], jobs, 2)[0], [('macos15', 1), ('macos26', 1)])
        self.assertEqual(controller.matching_profile({'labels': ['SELF-HOSTED', 'macOS', 'arm64', 'MACOS-27']}), 'xcode27')
        for unsupported in ([], ['macOS'], ['self-hosted'], ['ubuntu-latest'], ['macos-26', 'X64'], ['macos-15', 'custom']):
            self.assertIsNone(controller.matching_profile({'labels': unsupported}))

    def test_completed_running_or_already_assigned_jobs_do_not_create_hosts(self):
        jobs = [job(1, status='completed'), job(2, status='in_progress'), job(3, runner_name='assigned')]
        self.assertEqual(controller.plan_launches(set(), [], jobs, 12)[0], [])

    def test_busy_hosts_count_toward_limit_but_cannot_cover_more_jobs(self):
        busy = registration(busy=True)
        planned, _, covered, _ = controller.plan_launches({busy['name']}, [busy], [job(2)], 12)
        self.assertEqual(planned, [('macos15', 2)])
        self.assertEqual(covered['macos15'], 0)
        self.assertEqual(controller.plan_launches({busy['name']}, [busy], [job(2)], 1)[0], [])

    def test_pending_and_idle_hosts_cover_only_one_job_each_without_duplicates(self):
        active = {name(slot=1), name(slot=2)}
        jobs = [job(1), job(2), job(3), job(3)]
        planned, queued, covered, _ = controller.plan_launches(active, [registration(slot=2)], jobs, 12)
        self.assertEqual(planned, [('macos15', 3)])
        self.assertEqual(queued['macos15'], 3)
        self.assertEqual(covered['macos15'], 2)
        active.add(name(slot=3))
        self.assertEqual(controller.plan_launches(active, [registration(slot=2)], jobs, 12)[0], [])

    def test_completed_ephemeral_listener_does_not_appear_available_again(self):
        jobs = [job(1, status='completed', runner_name=name()), job(2)]
        self.assertEqual(controller.plan_launches({name()}, [registration()], jobs, 12)[0], [('macos15', 2)])

    def test_permanent_idle_runners_cover_compatible_jobs_without_mutation(self):
        permanent = registration()
        permanent['name'] = 'macos-15-1'
        planned, _, covered, _ = controller.plan_launches(set(), [permanent], [job(1), job(2), job(3, 'xcode27')], 12)
        self.assertEqual(planned, [('macos15', 1), ('xcode27', 1)])
        self.assertEqual(covered['macos15'], 1)
        self.assertEqual(permanent['name'], 'macos-15-1')

    def test_reads_jobs_of_queued_and_in_progress_runs_and_deduplicates(self):
        with patch.object(controller, 'pages', side_effect=[
            [{'id': 10}], [{'id': 10}, {'id': 20}], [job(1)], [job(2, 'macos26')],
        ]) as pages:
            self.assertEqual([j['id'] for j in controller.target_jobs()], [1, 2])
        paths = [call.args[0] for call in pages.call_args_list]
        self.assertIn('status=queued', paths[0])
        self.assertIn('status=in_progress', paths[1])
        self.assertEqual(paths.count(f'repos/{controller.TARGET}/actions/runs/10/jobs?filter=latest'), 1)

    def test_inventory_paginates_past_one_hundred_records(self):
        with patch.object(controller, 'gh', side_effect=[{'jobs': [job(n) for n in range(100)]}, {'jobs': [job(100)]}]) as api:
            self.assertEqual(len(controller.pages('jobs?filter=latest', 'jobs')), 101)
        self.assertTrue(api.call_args.args[0].endswith('&per_page=100&page=2'))

    def reconcile(self, runs, runners, environments, jobs, dry_run=False):
        with patch.object(controller, 'pages', side_effect=[runs, runners, environments]), \
                patch.object(controller, 'target_jobs', return_value=jobs), \
                patch.object(controller, 'gh') as api, patch.object(controller, 'launch') as launch, \
                patch.dict(controller.os.environ, {'HOST_CAPACITY': '12', 'DRY_RUN': str(dry_run).lower()}):
            controller.maintain()
        return api, launch

    def test_recent_completed_host_frees_slot_immediately_and_cleans_only_owned_state(self):
        recent = datetime.datetime.now(datetime.timezone.utc).isoformat()
        completed = {'id': 10, 'display_title': 'Managed runner ' + name(), 'status': 'completed', 'created_at': recent}
        permanent = registration(slot=2, status='offline')
        permanent['name'] = 'macos-15-1'
        api, launch = self.reconcile([completed], [registration(), permanent],
                                    [{'name': name(), 'created_at': recent}, {'name': 'unrelated', 'created_at': recent}], [job(2)])
        self.assertEqual([call.args for call in api.call_args_list], [
            (f'repos/{controller.TARGET}/actions/runners/1', 'DELETE'),
            (f'repos/{controller.HOST}/environments/{name()}', 'DELETE'),
        ])
        self.assertEqual(launch.call_args.args[0::2], (1, 'macos15'))

    def test_finished_last_job_cleans_up_without_a_replacement(self):
        recent = datetime.datetime.now(datetime.timezone.utc).isoformat()
        run = {'id': 10, 'display_title': 'Managed runner ' + name(), 'status': 'completed', 'created_at': recent}
        api, launch = self.reconcile([run], [], [{'name': name(), 'created_at': recent}], [])
        api.assert_called_once_with(f'repos/{controller.HOST}/environments/{name()}', 'DELETE')
        launch.assert_not_called()

    def test_dispatch_visibility_reservation_prevents_a_duplicate_host(self):
        recent = datetime.datetime.now(datetime.timezone.utc).isoformat()
        api, launch = self.reconcile([], [], [{'name': name(), 'created_at': recent}], [job(1)])
        api.assert_not_called()
        launch.assert_not_called()

    def test_stalled_boot_is_cancelled_without_overbooking_its_reserved_slot(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        run = {'id': 10, 'display_title': 'Managed runner ' + name(), 'status': 'in_progress', 'created_at': old}
        api, launch = self.reconcile([run], [], [{'name': name(), 'created_at': old}], [job(1), job(2)])
        api.assert_called_once_with(f'repos/{controller.HOST}/actions/runs/10/cancel', 'POST')
        self.assertEqual(launch.call_args.args[0::2], (2, 'macos15'))

    def test_queue_read_failure_cannot_mutate_or_launch_anything(self):
        with patch.object(controller, 'pages', side_effect=[[], [], []]), \
                patch.object(controller, 'target_jobs', side_effect=RuntimeError('API unavailable')), \
                patch.object(controller, 'gh') as api, patch.object(controller, 'launch') as launch:
            with self.assertRaises(RuntimeError):
                controller.maintain()
        api.assert_not_called()
        launch.assert_not_called()

    def test_dry_run_has_no_mutations_even_with_queue_or_stale_state(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        api, launch = self.reconcile([], [registration(status='offline')], [{'name': name(), 'created_at': old}], [job(1)], True)
        api.assert_not_called()
        launch.assert_not_called()

    def test_invalid_capacity_cannot_launch_hosts(self):
        for value in ('-1', '13'):
            with patch.dict(controller.os.environ, {'HOST_CAPACITY': value}), patch.object(controller, 'pages') as pages:
                with self.assertRaises(ValueError):
                    controller.maintain()
                pages.assert_not_called()

    def test_registration_secret_never_appears_in_dispatch_payload(self):
        calls = []
        def api(path, method='GET', data=None):
            calls.append((path, method, data))
            return {'token': 'private-registration'} if path.endswith('/registration-token') else None
        with patch.object(controller, 'gh', side_effect=api), patch.object(controller.subprocess, 'run') as command:
            controller.launch(12, datetime.datetime(2026, 11, 18, tzinfo=datetime.timezone.utc), 'macos26')
        self.assertEqual(command.call_args.kwargs['input'], b'private-registration')
        self.assertNotIn('private-registration', repr(calls))
        self.assertEqual(calls[-1][2]['inputs']['image'], PROFILES['macos26']['image'])


class SingleJobRunnerTests(unittest.TestCase):
    def test_registration_is_ephemeral_with_native_labels(self):
        with patch.object(runner.subprocess, 'run') as command:
            runner.configure_runner(Path('/runner'), 'xcode27', name('xcode27'), 'token', {}, None)
        args = command.call_args.args[0]
        self.assertIn('--ephemeral', args)
        self.assertNotIn('--disableupdate', args)
        self.assertEqual(args[args.index('--labels') + 1], ','.join(labels('xcode27')))

    def test_fast_job_finishes_without_starting_a_second_listener(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / '_diag').mkdir()
            def start(*args):
                (directory / '_diag' / 'Worker_1.log').touch()
                return Mock(poll=Mock(return_value=0))
            with patch.object(runner, 'start_runner', side_effect=start) as start_mock, patch.object(runner, 'stop'):
                self.assertEqual(runner.serve_job(directory, {}, None), 1)
            start_mock.assert_called_once()

    def test_idle_timeout_stops_host_and_ignores_old_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / '_diag').mkdir()
            (directory / '_diag' / 'Worker_old.log').touch()
            process = Mock(poll=Mock(return_value=None))
            with patch.object(runner, 'start_runner', return_value=process) as start, \
                    patch.object(runner, 'stop') as stop, patch.object(runner.time, 'monotonic', side_effect=[0, 600]):
                self.assertEqual(runner.serve_job(directory, {}, None), 0)
            start.assert_called_once()
            stop.assert_called_once_with(process)

    def test_running_job_can_finish_after_idle_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / '_diag').mkdir()
            def start(*args):
                (directory / '_diag' / 'Worker_1.log').touch()
                return Mock(poll=Mock(side_effect=[None, None, 0]))
            with patch.object(runner, 'start_runner', side_effect=start) as start_mock, \
                    patch.object(runner, 'stop'), patch.object(runner.time, 'sleep'), \
                    patch.object(runner.time, 'monotonic', side_effect=[0, 5, 8]):
                self.assertEqual(runner.serve_job(directory, {}, None, accept_seconds=5, max_seconds=10), 1)
            start_mock.assert_called_once()

    def test_listener_failure_and_hard_deadline_always_stop_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / '_diag').mkdir()
            for code in (1, None):
                process = Mock(poll=Mock(return_value=code))
                def start(*args):
                    (directory / '_diag' / f'Worker_{code}.log').touch()
                    return process
                with patch.object(runner, 'start_runner', side_effect=start), patch.object(runner, 'stop') as stop, \
                        patch.object(runner.time, 'monotonic', side_effect=[0, 11]):
                    with self.assertRaises(RuntimeError if code == 1 else TimeoutError):
                        runner.serve_job(directory, {}, None, max_seconds=10)
                stop.assert_called_once_with(process)


if __name__ == '__main__':
    unittest.main()
