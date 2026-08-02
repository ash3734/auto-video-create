"""
test_style_templates.py — feat/style-templates 단위 테스트

계정당 단일 subtitle_settings 를 이름 붙인 템플릿 최대 5개(subtitle_templates)로
확장하는 기능의 순수 로직 검증. S3 는 전부 mock 처리 (외부 의존성 없음).
pytest 없이 stdlib unittest 사용 (기존 test_cycle3_subtitle.py 와 동일 관행).
"""

import copy
import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 서버 루트를 sys.path 에 추가
_SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_ROOT not in sys.path:
    sys.path.insert(0, _SERVER_ROOT)


def _users_fixture():
    """users.json mock 데이터 — 각 테스트에서 deepcopy 해서 사용."""
    return [
        {
            "id": "legacy_user",
            "pw": "pw",
            "subscription_start": "2020-01-01",
            "subscription_end": "2099-01-01",
            "credits": 1000,
            # subtitle_templates 없음, legacy 단일 subtitle_settings 만 있음
            "subtitle_settings": {
                "title": {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
                "subtitle": {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
            },
        },
        {
            "id": "no_settings_user",
            "pw": "pw",
            "subscription_start": "2020-01-01",
            "subscription_end": "2099-01-01",
            "credits": 1000,
            # subtitle_settings 도, subtitle_templates 도 없음
        },
        {
            "id": "templated_user",
            "pw": "pw",
            "subscription_start": "2020-01-01",
            "subscription_end": "2099-01-01",
            "credits": 1000,
            "subtitle_templates": [
                {
                    "id": "tpl-1",
                    "name": "기본",
                    "title": {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
                    "subtitle": {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
                }
            ],
            # 레거시 필드가 남아있어도 subtitle_templates 가 있으면 그쪽을 신뢰
            "subtitle_settings": {
                "title": {"font_family": "Do Hyeon", "font_size": "L", "fill_color": "#000000"},
                "subtitle": {"font_family": "Do Hyeon", "font_size": "L", "fill_color": "#000000"},
            },
        },
        {
            "id": "five_templates_user",
            "pw": "pw",
            "subscription_start": "2020-01-01",
            "subscription_end": "2099-01-01",
            "credits": 1000,
            "subtitle_templates": [
                {
                    "id": f"tpl-{i}",
                    "name": f"템플릿 {i}",
                    "title": {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
                    "subtitle": {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
                }
                for i in range(5)
            ],
        },
    ]


class StyleTemplatesTestCase(unittest.TestCase):
    """공통 mock 셋업: load_json_from_s3 / _s3.put_object 를 patch."""

    def setUp(self):
        from services import subtitle_settings_service as svc

        self.svc = svc
        self._users = _users_fixture()

        self.load_patcher = patch.object(svc, "load_json_from_s3", return_value=copy.deepcopy(self._users))
        self.mock_load = self.load_patcher.start()
        self.addCleanup(self.load_patcher.stop)

        self.s3_patcher = patch.object(svc, "_s3", MagicMock())
        self.mock_s3 = self.s3_patcher.start()
        self.addCleanup(self.s3_patcher.stop)

    def _put_object_body(self):
        """put_object 호출 시 전달된 Body 를 파싱해 users 리스트로 반환."""
        _, kwargs = self.mock_s3.put_object.call_args
        return json.loads(kwargs["Body"].decode("utf-8"))

    def _find_user(self, users, user_id):
        return next(u for u in users if u["id"] == user_id)


# ─────────────────────────────────────────────
# 마이그레이션 (읽기 시)
# ─────────────────────────────────────────────

class TestMigration(StyleTemplatesTestCase):

    def test_legacy_user_migrated_on_get(self):
        """subtitle_templates 없고 legacy subtitle_settings 만 있으면 1개짜리 템플릿으로 변환."""
        templates = self.svc.get_subtitle_templates("legacy_user")
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["name"], "템플릿 1")
        self.assertIn("id", templates[0])
        self.assertEqual(templates[0]["title"]["font_family"], "Black Han Sans")
        self.assertEqual(templates[0]["subtitle"]["font_family"], "Noto Sans KR")

    def test_legacy_migration_not_persisted_on_get(self):
        """GET 만으로는 S3 에 쓰지 않는다 (lazy 영속화)."""
        self.svc.get_subtitle_templates("legacy_user")
        self.mock_s3.put_object.assert_not_called()

    def test_no_settings_user_returns_empty_list(self):
        """subtitle_settings 도 subtitle_templates 도 없으면 빈 리스트."""
        templates = self.svc.get_subtitle_templates("no_settings_user")
        self.assertEqual(templates, [])

    def test_templated_user_ignores_legacy_field(self):
        """subtitle_templates 가 이미 있으면 legacy subtitle_settings 는 무시."""
        templates = self.svc.get_subtitle_templates("templated_user")
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["id"], "tpl-1")
        self.assertEqual(templates[0]["title"]["font_family"], "Black Han Sans")  # legacy(Do Hyeon) 아님

    def test_unknown_user_returns_empty_list(self):
        templates = self.svc.get_subtitle_templates("nonexistent_user")
        self.assertEqual(templates, [])

    def test_legacy_migration_persisted_lazily_on_next_create(self):
        """마이그레이션은 다음 CRUD 저장 시점에 실제로 영속화된다."""
        self.svc.create_subtitle_template(
            "legacy_user",
            "새 템플릿",
            {"font_family": "Do Hyeon", "font_size": "S", "fill_color": "#111111"},
            {"font_family": "Do Hyeon", "font_size": "S", "fill_color": "#111111"},
        )
        saved_users = self._put_object_body()
        saved_user = self._find_user(saved_users, "legacy_user")
        # 기존 legacy 값 1개(마이그레이션) + 신규 1개 = 2개가 영속화됨
        self.assertEqual(len(saved_user["subtitle_templates"]), 2)
        self.assertEqual(saved_user["subtitle_templates"][0]["name"], "템플릿 1")
        self.assertEqual(saved_user["subtitle_templates"][1]["name"], "새 템플릿")


# ─────────────────────────────────────────────
# 생성 — 5개 제한
# ─────────────────────────────────────────────

class TestCreateSubtitleTemplate(StyleTemplatesTestCase):

    def test_create_success_returns_template_with_id(self):
        template = self.svc.create_subtitle_template(
            "no_settings_user",
            "내 스타일",
            {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
            {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
        )
        self.assertEqual(template["name"], "내 스타일")
        self.assertIn("id", template)
        self.mock_s3.put_object.assert_called_once()

    def test_create_persists_to_s3(self):
        self.svc.create_subtitle_template(
            "templated_user",
            "두번째",
            {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
            {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
        )
        saved_users = self._put_object_body()
        saved_user = self._find_user(saved_users, "templated_user")
        self.assertEqual(len(saved_user["subtitle_templates"]), 2)

    def test_create_rejects_when_limit_reached(self):
        """이미 5개면 TemplateLimitReachedError."""
        with self.assertRaises(self.svc.TemplateLimitReachedError):
            self.svc.create_subtitle_template(
                "five_templates_user",
                "여섯번째",
                {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
                {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
            )
        self.mock_s3.put_object.assert_not_called()

    def test_create_unknown_user_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            self.svc.create_subtitle_template(
                "nonexistent_user",
                "이름",
                {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
                {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
            )
        self.mock_s3.put_object.assert_not_called()


# ─────────────────────────────────────────────
# 수정
# ─────────────────────────────────────────────

class TestUpdateSubtitleTemplate(StyleTemplatesTestCase):

    def test_update_name_only(self):
        updated = self.svc.update_subtitle_template("templated_user", "tpl-1", name="바뀐 이름")
        self.assertEqual(updated["name"], "바뀐 이름")
        # title/subtitle 은 유지
        self.assertEqual(updated["title"]["font_family"], "Black Han Sans")

    def test_update_title_only(self):
        new_title = {"font_family": "Do Hyeon", "font_size": "L", "fill_color": "#222222"}
        updated = self.svc.update_subtitle_template("templated_user", "tpl-1", title=new_title)
        self.assertEqual(updated["title"], new_title)
        self.assertEqual(updated["name"], "기본")  # 이름 유지

    def test_update_persists_only_changed_template(self):
        self.svc.update_subtitle_template("templated_user", "tpl-1", name="변경됨")
        saved_users = self._put_object_body()
        saved_user = self._find_user(saved_users, "templated_user")
        self.assertEqual(saved_user["subtitle_templates"][0]["name"], "변경됨")

    def test_update_missing_template_raises_not_found(self):
        with self.assertRaises(self.svc.TemplateNotFoundError):
            self.svc.update_subtitle_template("templated_user", "no-such-id", name="x")
        self.mock_s3.put_object.assert_not_called()

    def test_update_unknown_user_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            self.svc.update_subtitle_template("nonexistent_user", "tpl-1", name="x")


# ─────────────────────────────────────────────
# 삭제
# ─────────────────────────────────────────────

class TestDeleteSubtitleTemplate(StyleTemplatesTestCase):

    def test_delete_success(self):
        # 2개 이상인 유저(five_templates_user)에서 삭제 — 마지막 1개 아님
        templates = self.svc.get_subtitle_templates("five_templates_user")
        target_id = templates[0]["id"]
        self.svc.delete_subtitle_template("five_templates_user", target_id)
        saved_users = self._put_object_body()
        saved_user = self._find_user(saved_users, "five_templates_user")
        self.assertEqual(len(saved_user["subtitle_templates"]), 4)
        self.assertNotIn(target_id, [t["id"] for t in saved_user["subtitle_templates"]])

    def test_delete_last_template_blocked(self):
        """마지막 남은 1개 템플릿 삭제는 서버가 차단 (최소 1개 유지 — PO 확정 2026-08-02)."""
        with self.assertRaises(self.svc.LastTemplateError):
            self.svc.delete_subtitle_template("templated_user", "tpl-1")
        self.mock_s3.put_object.assert_not_called()

    def test_delete_missing_template_raises_not_found(self):
        with self.assertRaises(self.svc.TemplateNotFoundError):
            self.svc.delete_subtitle_template("templated_user", "no-such-id")
        self.mock_s3.put_object.assert_not_called()

    def test_delete_unknown_user_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            self.svc.delete_subtitle_template("nonexistent_user", "tpl-1")

    def test_delete_from_legacy_migrated_list(self):
        """legacy 유저의 마이그레이션 id 가 결정적(uuid5)인지 + DELETE 가 그 id 를 인식하는지.

        GET 과 DELETE 는 각각 별도로 load_json_from_s3 를 호출(=별도로 마이그레이션)
        하므로, id 가 결정적(uuid5)이지 않으면 GET 에서 받은 id 로 DELETE 가 404 나는
        회귀가 발생한다 — 이 테스트는 그 회귀를 방지한다.

        (갱신) 마지막 1개 삭제는 이제 LastTemplateError 로 차단되므로, "id 를 인식했다"는
        것은 TemplateNotFoundError(404)가 아니라 LastTemplateError 가 나오는 것으로 검증.
        """
        templates = self.svc.get_subtitle_templates("legacy_user")
        migrated_id = templates[0]["id"]

        # 마이그레이션 id 는 GET 을 다시 호출해도 항상 동일해야 한다 (결정적 uuid5).
        templates_again = self.svc.get_subtitle_templates("legacy_user")
        self.assertEqual(templates_again[0]["id"], migrated_id)

        # 결정적 id 가 인식됨 → NotFound(회귀)가 아니라 마지막 1개 차단 에러
        with self.assertRaises(self.svc.LastTemplateError):
            self.svc.delete_subtitle_template("legacy_user", migrated_id)


# ─────────────────────────────────────────────
# validate_text_style (부분 검증 공개 wrapper)
# ─────────────────────────────────────────────

class TestValidateTextStyle(unittest.TestCase):

    def test_valid_style_no_errors(self):
        from services.subtitle_settings_service import validate_text_style
        style = {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"}
        errors = validate_text_style(style, {"Noto Sans KR"})
        self.assertEqual(errors, [])

    def test_invalid_style_returns_errors(self):
        from services.subtitle_settings_service import validate_text_style
        style = {"font_family": "Noto Sans KR", "font_size": "XL", "fill_color": "notacolor"}
        errors = validate_text_style(style, {"Noto Sans KR"})
        self.assertTrue(any("font_size" in e for e in errors))
        self.assertTrue(any("fill_color" in e for e in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
