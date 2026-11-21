import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import managed_pool as controller
from managed_profiles import PROFILES, identify, labels, validate
from managed_runner import validate_namespace_shape


class ManagedMacOSTests(unittest.TestCase):
    def test_namespace_host_labels_select_requested_os_and_shape(self):
        expected = {
            'macos15': 'nscloud-macos-sequoia-stable-arm64-4x7',
            'macos26': 'nscloud-macos-tahoe-arm64-4x7',
            'xcode27': 'nscloud-macos-goldengate-arm64-4x7',
        }
        self.assertEqual({key: PROFILES[key]['image'] for key in expected}, expected)
        validate_namespace_shape(4, 7 * 1024 ** 3)
        validate_namespace_shape(4, 7_000_000_000)
        for cpus, memory in [(6, 7 * 1024 ** 3), (4, 4 * 1024 ** 3), (4, 14 * 1024 ** 3)]:
            with self.assertRaises(ValueError):
                validate_namespace_shape(cpus, memory)

    def test_profiles_validate_native_os_and_architecture_before_registration(self):
        for key, version, expected in [
            ('macos15', '15.7.2', ['macos-15', 'macos-15-arm64']),
            ('macos26', '26.7.2', ['macos-26', 'macos-26-arm64']),
            ('xcode27', '27.2', ['xcode-27', 'macos-27', 'macos-27-arm64']),
        ]:
            with self.subTest(profile=key):
                self.assertEqual(labels(key), ['self-hosted', 'macOS', 'ARM64', *expected])
                validate(key, 'Darwin', 'arm64', version)
                for system, machine, wrong_version in [
                    ('Darwin', 'x86_64', version), ('Linux', 'arm64', version),
                    ('Darwin', 'arm64', '14.8'),
                ]:
                    with self.assertRaises(ValueError):
                        validate(key, system, machine, wrong_version)
        with self.assertRaises(ValueError):
            validate('xcode27', 'Darwin', 'arm64', '26.7.2')

    def test_dispatch_selects_matching_native_image_and_private_environment(self):
        for key in ('macos15', 'macos26', 'xcode27'):
            with self.subTest(profile=key), patch.object(controller, 'gh') as api, \
                    patch.object(controller, 'create_environment') as create, \
                    patch.object(controller, 'refresh_registration') as refresh:
                controller.launch(1, datetime.datetime(2026, 11, 13, tzinfo=datetime.timezone.utc), key)
                path, method, data = api.call_args.args
                self.assertEqual((path, method),
                                 (f'repos/{controller.HOST}/actions/workflows/managed-runner.yml/dispatches', 'POST'))
                self.assertEqual(data['inputs']['image'], PROFILES[key]['image'])
                self.assertEqual(identify(data['inputs']['pool']), (key, 1))
                create.assert_called_once_with(data['inputs']['pool'])
                refresh.assert_called_once_with(data['inputs']['pool'])


if __name__ == '__main__':
    unittest.main()
