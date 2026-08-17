"""크레딧 차감 트리거 — 단위 테스트 (2026-08-17).

## 이 테스트가 막는 것

차감 조건이 `response.status_code == 200` 이었는데 Creatomate 는 렌더 생성에
**202 Accepted** 를 반환한다(렌더가 비동기로 시작되므로). 그래서 차감 블록이
**한 번도 실행된 적이 없었다** — prod 최근 30일 기준 렌더 성공 10건에 차감 0건,
S3 크레딧 이력은 2025-10 이후 비어 있었다.

진입 시 잔액 체크만 있고 차감이 없으면 크레딧 기반 유료 유저는 사실상 무제한이 된다.
돈과 직결되므로 상태 코드별로 못 박는다.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import create_creatomate_video as ccv  # noqa: E402


def _resp(status, body):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = body
    r.text = ""
    return r


def _run(status, body, user_id="payer"):
    """차감 호출 여부를 반환: (deduct_mock, stdout)"""
    with mock.patch.object(ccv, "check_user_credits", return_value=True), \
         mock.patch.object(ccv, "deduct_credits", return_value=True) as deduct, \
         mock.patch.object(ccv.requests, "post", return_value=_resp(status, body)):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ccv.create_creatomate_video(["a.mp3"], ["s"], user_id=user_id, scene_count=5)
    return deduct, buf.getvalue()


RENDER_LIST = [{"id": "render-abc", "status": "planned"}]
RENDER_DICT = {"id": "render-abc", "status": "planned"}


class TestDeductionTriggers(unittest.TestCase):
    def test_202_deducts(self):
        """실제 Creatomate 응답 코드 — 이게 이 버그의 핵심이다."""
        deduct, out = _run(202, RENDER_LIST)
        deduct.assert_called_once_with("payer", 1000, "video_generation")
        self.assertIn("크레딧 차감 완료", out)

    def test_200_still_deducts(self):
        """기존 동작도 유지되어야 한다 (회귀 방지)."""
        deduct, _ = _run(200, RENDER_LIST)
        deduct.assert_called_once()

    def test_201_deducts(self):
        deduct, _ = _run(201, RENDER_DICT)
        deduct.assert_called_once()

    def test_dict_response_shape_deducts(self):
        """응답이 리스트가 아니라 딕셔너리로 와도 동작해야 한다."""
        deduct, _ = _run(202, RENDER_DICT)
        deduct.assert_called_once()


class TestNoDeduction(unittest.TestCase):
    def test_no_render_id_does_not_deduct(self):
        """렌더가 시작되지 않았으면 차감하면 안 된다 — 돈을 잘못 걷는 쪽이 더 나쁘다."""
        deduct, _ = _run(202, [{"status": "planned"}])  # id 없음
        deduct.assert_not_called()

    def test_empty_response_does_not_deduct(self):
        deduct, _ = _run(202, [])
        deduct.assert_not_called()

    def test_anonymous_does_not_deduct(self):
        deduct, _ = _run(202, RENDER_LIST, user_id=None)
        deduct.assert_not_called()

    def test_error_status_does_not_deduct(self):
        """4xx/5xx 는 위에서 이미 반환되므로 여기까지 오지 않는다."""
        for status in (400, 402, 500):
            deduct, _ = _run(status, {"message": "nope"})
            deduct.assert_not_called()


class TestDeductionFailureAlerts(unittest.TestCase):
    def test_failed_deduction_alerts(self):
        """렌더는 시작됐는데 차감이 실패하면 돈이 샌다 — 반드시 알려야 한다."""
        with mock.patch.object(ccv, "check_user_credits", return_value=True), \
             mock.patch.object(ccv, "deduct_credits", return_value=False), \
             mock.patch.object(ccv.requests, "post", return_value=_resp(202, RENDER_LIST)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                ccv.create_creatomate_video(["a.mp3"], ["s"], user_id="payer", scene_count=5)
        out = buf.getvalue()
        self.assertIn("[ALERT]", out)
        self.assertIn("source=credits", out)
        self.assertIn("render_id=render-abc", out)


class TestExtractRenderId(unittest.TestCase):
    def test_list_shape(self):
        self.assertEqual(ccv._extract_render_id([{"id": "x"}]), "x")

    def test_dict_shape(self):
        self.assertEqual(ccv._extract_render_id({"id": "x"}), "x")

    def test_missing_and_malformed(self):
        for bad in (None, [], {}, [{}], "string", [None], 42):
            self.assertIsNone(ccv._extract_render_id(bad), f"{bad!r} 에서 None 이 아님")


if __name__ == "__main__":
    unittest.main()
