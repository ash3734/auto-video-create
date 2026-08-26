"""S3 자격증명 회귀 테스트 (2026-08-27).

## 무엇을 막는가

람다는 실행 역할의 **임시 자격증명**을 환경변수로 주입한다 — access key,
secret key, 그리고 **session token**. 세 개가 한 세트라, 토큰 없이 앞의 두 개만
넘기면 AWS 가 `InvalidAccessKeyId` 로 거부한다.

    boto3.client("s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))

이 형태가 세 모듈에 있었고, 그래서 **람다에서 S3 쓰기가 한 번도 성공한 적이 없다.**
읽기는 자격증명을 안 넘기는 별도 경로라 멀쩡해서, "로그인은 되는데 저장만 안 되는"
형태로만 드러났다. 실제 피해:

  - 비밀번호 변경 실패 (유저 ssonek, 2026-08-27 07:54 / 07:56)
  - 크레딧 차감이 S3 에 반영되지 않음
  - 크레딧 이력이 저장되지 않아 일일 리포트의 '성공' 이 항상 0

로컬에서는 장기 키(세션 토큰 없음)를 쓰므로 같은 코드가 잘 돌아간다. **로컬 검증
만으로는 절대 잡히지 않는 종류의 버그**라서, 소스 수준에서 못 박아 둔다.
"""
import ast
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SERVER_ROOT = pathlib.Path(__file__).resolve().parent.parent

# 로컬에서 사람이 직접 돌리는 관리 스크립트는 장기 키를 쓰므로 대상이 아니다.
EXCLUDED = {"scripts", "tests", "lambda"}


def _python_files():
    for path in SERVER_ROOT.rglob("*.py"):
        rel = path.relative_to(SERVER_ROOT)
        if rel.parts and rel.parts[0] in EXCLUDED:
            continue
        yield path


class TestNoExplicitCredentials(unittest.TestCase):
    def test_no_module_passes_key_without_session_token(self):
        """boto3 클라이언트에 access key 를 넘기면서 세션 토큰을 빠뜨리지 않는다."""
        offenders = []
        for path in _python_files():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                if name not in ("client", "resource"):
                    continue
                kwargs = {kw.arg for kw in node.keywords if kw.arg}
                if "aws_access_key_id" in kwargs and "aws_session_token" not in kwargs:
                    rel = path.relative_to(SERVER_ROOT)
                    offenders.append(f"{rel}:{node.lineno}")
        self.assertEqual(
            offenders, [],
            "자격증명을 직접 넘기려면 aws_session_token 도 함께 넘겨야 한다. "
            "람다에서는 그냥 넘기지 말고 utils.s3_utils.s3_client 를 쓸 것. "
            f"위반: {offenders}",
        )


class TestS3ClientUsesDefaultChain(unittest.TestCase):
    def test_client_built_without_credential_kwargs(self):
        """s3_client 는 자격증명 인자를 넘기지 않는다 (기본 체인에 위임)."""
        from utils import s3_utils

        with mock.patch.object(s3_utils.boto3, "client") as m:
            s3_utils.s3_client()
        m.assert_called_once()
        _, kwargs = m.call_args
        for forbidden in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token"):
            self.assertNotIn(forbidden, kwargs)
        self.assertEqual(kwargs.get("region_name"), "ap-northeast-2")

    def test_lambda_env_yields_session_token(self):
        """람다처럼 세 값이 주입된 환경에서, 만들어진 클라이언트가 토큰을 갖는다.

        이게 실제 실패 조건이었다 — 토큰이 빠지면 InvalidAccessKeyId 가 난다.

        boto3 는 기본 세션(`boto3.DEFAULT_SESSION`)을 만들어 재사용하고 자격증명을
        거기에 캐시한다. 다른 테스트가 먼저 세션을 만들어 두면 여기서 환경변수를
        바꿔도 반영되지 않으므로, 이 테스트 동안만 세션을 비웠다가 되돌린다.
        """
        from utils import s3_utils

        # 값을 **일부러 AWS 키 형식이 아니게** 둔다. 진짜처럼 보이는 값(ASIA/AKIA +
        # 16자)을 쓰면 GitHub 시크릿 스캐너가 실제 유출로 오인해 알림을 띄운다.
        # 2026-08-27 에 ASIAFAKE... 로 뒀다가 실제로 경보가 떴다. botocore 는 형식을
        # 검증하지 않으므로 아무 문자열이나 그대로 왕복한다.
        fake_lambda_env = {
            "AWS_ACCESS_KEY_ID": "not-a-real-key-id",
            "AWS_SECRET_ACCESS_KEY": "not-a-real-secret",
            "AWS_SESSION_TOKEN": "not-a-real-token",
            "AWS_DEFAULT_REGION": "ap-northeast-2",
        }
        saved = s3_utils.boto3.DEFAULT_SESSION
        s3_utils.boto3.DEFAULT_SESSION = None
        try:
            with mock.patch.dict(os.environ, fake_lambda_env, clear=False):
                client = s3_utils.s3_client()
                creds = client._request_signer._credentials
                self.assertEqual(creds.token, "not-a-real-token")
                self.assertEqual(creds.access_key, "not-a-real-key-id")
        finally:
            s3_utils.boto3.DEFAULT_SESSION = saved


class TestWritersUseTheHelper(unittest.TestCase):
    """쓰기를 하는 모듈이 헬퍼를 거치는지 확인 — 개별 재발을 막는다."""

    def test_account_service_client_is_helper_built(self):
        with mock.patch("utils.s3_utils.boto3.client") as m:
            import importlib

            from services import account_service

            importlib.reload(account_service)
        self.assertTrue(m.called)
        for _, kwargs in m.call_args_list:
            self.assertNotIn("aws_access_key_id", kwargs)


if __name__ == "__main__":
    unittest.main()
