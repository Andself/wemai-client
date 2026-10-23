import unittest
from unittest.mock import patch
from types import SimpleNamespace
import window_binding
from safety_policy import BindingError, GroupPolicy, WindowIdentity


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.policy = GroupPolicy(('test-group',), True)

    def test_only_explicit_group(self):
        self.assertTrue(self.policy.inbound(dict(type='inbound', is_group=True, chat='test-group')))
        for flag in (False, None, 1, 'true'):
            self.assertFalse(self.policy.inbound(dict(type='inbound', is_group=flag, chat='test-group')))

    def test_other_group_denied(self):
        self.assertFalse(self.policy.inbound(dict(type='inbound', is_group=True, chat='other')))

    def test_empty_allowlist_denies(self):
        self.assertFalse(GroupPolicy(()).inbound(dict(type='inbound', is_group=True, chat='test-group')))

    def test_dry_mode_denies_send(self):
        self.assertFalse(GroupPolicy(('test-group',)).outbound(dict(type='outbound', receiver='test-group', segments=[{}])))

    def test_only_normal_group_output(self):
        self.assertTrue(self.policy.outbound(dict(type='outbound', receiver='test-group', segments=[{}])))
        self.assertFalse(self.policy.outbound(dict(type='outbound', receiver='private', segments=[{}])))

    def test_extra_commands_denied(self):
        for command in ('moment_post', 'moment_read', 'friend_approve', 'friend_dismiss', 'inbound'):
            self.assertFalse(self.policy.outbound(dict(type=command, receiver='test-group', segments=[{}])))

    def test_remote_cannot_expand(self):
        self.assertEqual(self.policy.remote_groups(['test-group', 'private', 'another']), ['test-group'])

    def test_exact_group_name(self):
        self.assertFalse(self.policy.outbound(dict(type='outbound', receiver='test-group ', segments=[{}])))

    def test_window_reuse_denied(self):
        b = WindowIdentity(100, 200, 300)
        for current in (WindowIdentity(101, 200, 300), WindowIdentity(100, 201, 300), WindowIdentity(100, 200, 301)):
            with self.assertRaises(BindingError):
                b.validate(current)

    def test_missing_binding_denied(self):
        b = WindowIdentity(0, 0, 0)
        with self.assertRaises(BindingError):
            b.validate(b)

    def test_same_identity_accepted(self):
        b = WindowIdentity(100, 200, 300)
        b.validate(b)

    def test_no_automatic_window_selection(self):
        with patch.object(window_binding, '_identity', None):
            with self.assertRaises(BindingError):
                window_binding.assert_bound()

    def test_account_mismatch_rejected(self):
        b = WindowIdentity(100, 200, 300)
        for info in ({'昵称': 'other', '微信号': 'expected-id'},
                     {'昵称': 'expected', '微信号': 'other-id'}, {}):
            fake = SimpleNamespace(Contacts=SimpleNamespace(check_my_info=lambda **kw: info))
            with patch.dict('sys.modules', {'pyweixin': fake}), \
                 patch.object(window_binding, '_identity', b), \
                 patch.object(window_binding, '_nickname', 'expected'), \
                 patch.object(window_binding, '_account_id', 'expected-id'), \
                 patch.object(window_binding, 'current_identity', return_value=b):
                with self.assertRaises(BindingError):
                    window_binding.verify_account()

    def test_verified_account_accepted(self):
        b = WindowIdentity(100, 200, 300)
        fake = SimpleNamespace(Contacts=SimpleNamespace(check_my_info=lambda **kw: {'昵称': 'expected', '微信号': 'expected-id'}))
        with patch.dict('sys.modules', {'pyweixin': fake}), \
             patch.object(window_binding, '_identity', b), \
             patch.object(window_binding, '_nickname', 'expected'), \
             patch.object(window_binding, '_account_id', 'expected-id'), \
             patch.object(window_binding, 'current_identity', return_value=b):
            window_binding.verify_account()


if __name__ == '__main__':
    unittest.main()
