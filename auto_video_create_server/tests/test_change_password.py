"""비밀번호 변경 — 단위 테스트.

현재 비밀번호 검증 후에만 변경되며, 실패 시 S3 저장이 일어나지 않아야 한다.
(비밀번호는 현재 평문 저장 — 기존 구조 유지)
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import account_service as acc  # noqa: E402


class ChangePasswordTestCase(unittest.TestCase):

    def setUp(self):
        self.users = [
            {"id": "alice", "pw": "oldpassword1", "subscription_start": "2020-01-01",
             "subscription_end": "2099-12-31"},
            {"id": "bob", "pw": "bobsecret123", "subscription_start": "2020-01-01",
             "subscription_end": "2020-12-31"},  # 만료 계정
        ]
        self.load = mock.patch.object(acc, "load_json_from_s3", return_value=self.users)
        self.load.start(); self.addCleanup(self.load.stop)
        self.s3 = mock.patch.object(acc, "s3").start(); self.addCleanup(mock.patch.stopall)

    def _saved(self):
        """put_object 로 저장된 users 를 파싱."""
        import json
        self.s3.put_object.assert_called_once()
        return json.loads(self.s3.put_object.call_args.kwargs["Body"].decode("utf-8"))


class TestSuccess(ChangePasswordTestCase):

    def test_success_updates_password(self):
        self.assertEqual(acc.change_password("alice", "oldpassword1", "brandnewpw9"), "success")
        saved = self._saved()
        self.assertEqual(next(u for u in saved if u["id"] == "alice")["pw"], "brandnewpw9")

    def test_other_users_untouched(self):
        acc.change_password("alice", "oldpassword1", "brandnewpw9")
        saved = self._saved()
        self.assertEqual(next(u for u in saved if u["id"] == "bob")["pw"], "bobsecret123")

    def test_expired_subscription_can_still_change(self):
        """구독이 만료돼도 비밀번호는 바꿀 수 있어야 한다."""
        self.assertEqual(acc.change_password("bob", "bobsecret123", "bobnewpass1"), "success")


class TestRejection(ChangePasswordTestCase):

    def test_wrong_current_password(self):
        self.assertEqual(acc.change_password("alice", "wrongpw12345", "brandnewpw9"), "invalid")
        self.s3.put_object.assert_not_called()

    def test_unknown_user(self):
        self.assertEqual(acc.change_password("nobody", "whatever1234", "brandnewpw9"), "invalid")
        self.s3.put_object.assert_not_called()

    def test_unknown_user_and_wrong_pw_give_same_code(self):
        """계정 존재 여부가 응답으로 드러나지 않아야 한다."""
        a = acc.change_password("nobody", "x" * 12, "brandnewpw9")
        b = acc.change_password("alice", "wrongpw12345", "brandnewpw9")
        self.assertEqual(a, b)

    def test_same_as_current(self):
        self.assertEqual(acc.change_password("alice", "oldpassword1", "oldpassword1"), "same")
        self.s3.put_object.assert_not_called()

    def test_too_short(self):
        self.assertEqual(acc.change_password("alice", "oldpassword1", "short"), "too_short")
        self.s3.put_object.assert_not_called()

    def test_min_length_boundary(self):
        exactly_min = "a" * acc.MIN_PASSWORD_LENGTH
        self.assertEqual(acc.change_password("alice", "oldpassword1", exactly_min), "success")

    def test_one_below_min_rejected(self):
        below = "a" * (acc.MIN_PASSWORD_LENGTH - 1)
        self.assertEqual(acc.change_password("alice", "oldpassword1", below), "too_short")
        self.s3.put_object.assert_not_called()

    def test_non_string_new_pw(self):
        self.assertEqual(acc.change_password("alice", "oldpassword1", None), "too_short")
        self.s3.put_object.assert_not_called()

    def test_validation_runs_before_s3_read(self):
        """짧은 비밀번호는 S3 조회조차 하지 않는다 (불필요한 I/O 방지)."""
        acc.load_json_from_s3.reset_mock()
        acc.change_password("alice", "oldpassword1", "x")
        acc.load_json_from_s3.assert_not_called()


class TestErrorHandling(ChangePasswordTestCase):

    def test_s3_failure_returns_error(self):
        self.s3.put_object.side_effect = Exception("S3 다운")
        self.assertEqual(acc.change_password("alice", "oldpassword1", "brandnewpw9"), "error")


if __name__ == "__main__":
    unittest.main()
