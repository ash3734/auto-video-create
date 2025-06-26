from fastapi import APIRouter
from pydantic import BaseModel
from services.account_service import authenticate_user

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
    if user:
        return LoginResponse(status="success", id=user["id"], subscription_start=user["subscription_start"], subscription_end=user["subscription_end"])
    else:
        return LoginResponse(status="fail", reason="invalid credentials") 