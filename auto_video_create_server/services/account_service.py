# PEP 604 (`dict | str | None`) 어노테이션이 Python 3.9 에서도 import 가능하도록
# 어노테이션을 지연 평가한다. Lambda 는 3.11 이라 동작 영향 없고, 로컬(3.9)에서
# 단위 테스트를 돌릴 수 있게 된다.
from __future__ import annotations

from utils.s3_utils import load_json_from_s3
from datetime import datetime
import boto3
import json
import os

def authenticate_user(user_id: str, pw: str) -> dict | str | None:
    users = load_json_from_s3("blog-to-short-form-users", "users.json")
    for user in users:
        if user["id"] == user_id and user["pw"] == pw:
            # 구독 기간 체크
            today = datetime.utcnow().date()
            start = datetime.strptime(user["subscription_start"], "%Y-%m-%d").date()
            end = datetime.strptime(user["subscription_end"], "%Y-%m-%d").date()
            if not (start <= today <= end):
                return "expired"
            return user
    return None

MIN_PASSWORD_LENGTH = 8


def change_password(user_id: str, current_pw: str, new_pw: str) -> str:
    """비밀번호 변경. 현재 비밀번호가 맞아야 한다.

    반환값:
        "success"      변경 완료
        "invalid"      사용자 없음 또는 현재 비밀번호 불일치 (구분해서 알려주지 않는다 — 계정 존재 여부 노출 방지)
        "same"         새 비밀번호가 현재와 동일
        "too_short"    새 비밀번호가 최소 길이 미만
        "error"        S3 등 내부 오류

    NOTE: 비밀번호는 현재 users.json 에 평문으로 저장된다(기존 구조 유지).
    추후 해싱 도입 시 이 함수에서 해시 저장으로 바꾸고, authenticate_user 에서
    "저장값이 해시면 해시 검증, 아니면 평문 비교 후 해시로 승격"하는 lazy migration
    을 붙이면 기존 유저 영향 없이 전환할 수 있다.
    비밀번호 값 자체는 절대 로그에 남기지 않는다.
    """
    if not isinstance(new_pw, str) or len(new_pw) < MIN_PASSWORD_LENGTH:
        return "too_short"
    if current_pw == new_pw:
        return "same"

    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        for user in users:
            if user["id"] == user_id:
                if user.get("pw") != current_pw:
                    print(f"[change_password] 현재 비밀번호 불일치 (user={user_id})")
                    return "invalid"
                user["pw"] = new_pw
                s3.put_object(
                    Bucket=BUCKET_USERS,
                    Key=KEY_USERS,
                    Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"),
                )
                print(f"[change_password] 변경 완료 (user={user_id})")
                return "success"
        print(f"[change_password] 사용자 없음 (user={user_id})")
        return "invalid"
    except Exception as e:
        print(f"[change_password] 실패 (user={user_id}): {e}")
        return "error"


def get_user_if_active(user_id: str) -> dict | None:
    """사용자 존재 + 구독 활성 여부 확인.

    cycle-2.1 BUG-003 fix (ADR-6 보강):
    - ENV=test 환경에서는 구독 만료 체크를 건너뜀 (`check/deduct_credits` 와 일관)
    - 사용자가 users.json 에 존재하면 만료일 무관 활성으로 간주
    - test 계정 운영 시 만료 갱신을 PO 가 매번 안 해도 됨
    """
    users = load_json_from_s3("blog-to-short-form-users", "users.json")
    is_test_env = os.environ.get("ENV", "").lower() == "test"
    for user in users:
        if user["id"] == user_id:
            if is_test_env:
                # cycle-2.1: test 환경은 만료 체크 우회. 존재만 확인.
                return user
            today = datetime.utcnow().date()
            start = datetime.strptime(user["subscription_start"], "%Y-%m-%d").date()
            end = datetime.strptime(user["subscription_end"], "%Y-%m-%d").date()
            if start <= today <= end:
                return user
            else:
                return None
    return None

# 크레딧 관련 함수들
BUCKET_USERS = "blog-to-short-form-users"
BUCKET_CREDITS = "blog-to-short-form-credits"
KEY_USERS = "users.json"

s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ap-northeast-2"
)

def get_current_credits(user_id: str) -> int:
    """사용자의 현재 크레딧 조회"""
    users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
    for user in users:
        if user["id"] == user_id:
            return user.get("credits", 0)
    return 0

def check_user_credits(user_id: str, required_credits: int = 1000) -> bool:
    """사용자의 크레딧이 충분한지 체크.

    cycle-2 (ADR-6): ENV=test 환경에서는 항상 True (deduct_credits 와 일관).
    """
    if os.environ.get("ENV", "").lower() == "test":
        return True
    current_credits = get_current_credits(user_id)
    return current_credits >= required_credits

def save_credit_record(credit_record: dict):
    """크레딧 변경 이력 저장"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"credits/{credit_record['user_id']}/{timestamp}.json"
    
    s3.put_object(
        Bucket=BUCKET_CREDITS, 
        Key=key, 
        Body=json.dumps(credit_record, ensure_ascii=False, indent=2).encode("utf-8")
    )

def deduct_credits(user_id: str, amount: int = 1000, reason: str = "video_generation") -> bool:
    """크레딧 차감.

    cycle-2 (ADR-6): ENV=test 환경에서는 차감 건너뜀.
    KPI funnel (test 무료 시도 → prod 결제) 의 본질이므로 정책으로 강제.
    """
    # cycle-2: ENV=test 일관 우회
    if os.environ.get("ENV", "").lower() == "test":
        print(f"[deduct_credits] ENV=test — 차감 건너뜀 (user={user_id}, amount={amount}, reason={reason})")
        return True

    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        user_found = False
        
        for user in users:
            if user["id"] == user_id:
                current_credits = user.get("credits", 0)
                
                if current_credits < amount:
                    print(f"[!] 크레딧 부족. 현재: {current_credits}, 필요: {amount}")
                    return False
                
                new_credits = current_credits - amount
                user["credits"] = new_credits
                user_found = True
                
                # 이력 기록
                credit_record = {
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "change_type": "deduct",
                    "amount": -amount,
                    "reason": reason
                }
                save_credit_record(credit_record)
                
                print(f"[-] {user_id}에서 {amount} 크레딧 차감 완료. 현재 크레딧: {new_credits}")
                break
        
        if not user_found:
            print(f"[!] 사용자 {user_id}를 찾을 수 없습니다.")
            return False
        
        # S3에 업데이트된 사용자 데이터 저장
        s3.put_object(
            Bucket=BUCKET_USERS, 
            Key=KEY_USERS, 
            Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8")
        )
        
        return True
        
    except Exception as e:
        print(f"[!] 크레딧 차감 실패: {e}")
        return False