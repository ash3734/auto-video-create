from fastapi import APIRouter
from pydantic import BaseModel
from services.account_service import authenticate_user, change_password, MIN_PASSWORD_LENGTH

router = APIRouter()

class LoginRequest(BaseModel):
    id: str
    pw: str

class LoginResponse(BaseModel):
    status: str
    id: str = None
    subscription_start: str = None
    subscription_end: str = None
    reason: str = None

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = authenticate_user(req.id, req.pw)
    if user == "expired":
        return LoginResponse(status="fail", reason="구독 기간이 만료되었습니다. 관리자에게 문의하세요.")
    if user:
        return LoginResponse(status="success", id=user["id"], subscription_start=user["subscription_start"], subscription_end=user["subscription_end"])
    else:
        return LoginResponse(status="fail", reason="invalid credentials")


class ChangePasswordRequest(BaseModel):
    id: str
    current_pw: str
    new_pw: str


class ChangePasswordResponse(BaseModel):
    status: str
    reason: str = None


# 결과 코드 → 사용자에게 보여줄 메시지 (해요체)
_CHANGE_PW_MESSAGES = {
    "invalid": "아이디 또는 현재 비밀번호가 올바르지 않아요.",
    "same": "새 비밀번호가 현재 비밀번호와 같아요.",
    "too_short": f"새 비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 해요.",
    "error": "비밀번호를 변경할 수 없어요. 잠시 후 다시 시도해주세요.",
}


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password_endpoint(req: ChangePasswordRequest):
    """POST /api/account/change-password

    현재 비밀번호를 검증한 뒤 새 비밀번호로 변경한다.
    구독 만료 여부와 무관하게 변경 가능 (만료 계정도 비밀번호는 바꿀 수 있어야 함).
    """
    result = change_password(req.id, req.current_pw, req.new_pw)
    if result == "success":
        return ChangePasswordResponse(status="success")
    return ChangePasswordResponse(
        status="fail",
        reason=_CHANGE_PW_MESSAGES.get(result, _CHANGE_PW_MESSAGES["error"]),
    )