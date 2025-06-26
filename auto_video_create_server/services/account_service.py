from utils.s3_utils import load_json_from_s3

def authenticate_user(user_id: str, pw: str) -> dict | None:
    users = load_json_from_s3("blog-to-short-form-users", "users.json")
    for user in users:
        if user["id"] == user_id and user["pw"] == pw:
            return user
    return None 