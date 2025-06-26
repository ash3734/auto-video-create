from utils.s3_utils import load_json_from_s3
from datetime import datetime

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

def get_user_if_active(user_id: str) -> dict | None:
    users = load_json_from_s3("blog-to-short-form-users", "users.json")
    for user in users:
        if user["id"] == user_id:
            today = datetime.utcnow().date()
            start = datetime.strptime(user["subscription_start"], "%Y-%m-%d").date()
            end = datetime.strptime(user["subscription_end"], "%Y-%m-%d").date()
            if start <= today <= end:
                return user
            else:
                return None
    return None 