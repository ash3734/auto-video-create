import boto3
import json

REGION = "ap-northeast-2"


def s3_client():
    """S3 클라이언트. **자격증명을 직접 넘기지 않는다** (2026-08-27).

    ## 왜 이게 중요한가

    람다는 실행 역할의 **임시 자격증명**을 런타임에 환경변수로 주입한다 —
    `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, 그리고 **`AWS_SESSION_TOKEN`**.
    임시 자격증명은 세 개가 한 세트라, 세션 토큰 없이 앞의 두 개만 제시하면
    AWS 가 거부한다.

        boto3.client("s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
        → botocore.exceptions.ClientError: InvalidAccessKeyId

    이 형태가 account_service / image_mirror / ai_background 에 있었고, 그래서
    **람다에서 S3 쓰기가 한 번도 성공한 적이 없다.** 읽기는 `boto3.client("s3")`
    를 쓰는 별도 경로라 멀쩡했기 때문에 "로그인은 되는데 저장만 안 되는" 형태로
    드러났다. 2026-08-27 유저 ssonek 의 비밀번호 변경 실패로 처음 표면화됐다.

    로컬에서는 장기 키(세션 토큰 없음)를 쓰므로 같은 코드가 잘 동작한다.
    그래서 로컬 검증만으로는 절대 잡히지 않는 종류의 버그다.

    ## 그래서 어떻게

    기본 자격증명 체인에 맡긴다. 람다에서는 실행 역할(세션 토큰 포함)을,
    로컬에서는 프로필/환경변수를 알아서 집는다. 양쪽 다 동작하고,
    자격증명을 코드가 만질 일이 없어진다.
    """
    return boto3.client("s3", region_name=REGION)


def load_json_from_s3(bucket: str, key: str) -> list:
    obj = s3_client().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())
