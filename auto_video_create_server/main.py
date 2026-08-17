from fastapi import FastAPI
from api.blog import router as blog_router
from api.account import router as account_router
from mangum import Mangum
from fastapi.responses import JSONResponse
from fastapi import Request
import traceback
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

app.include_router(blog_router, prefix="/api/blog")
app.include_router(account_router, prefix="/api/account")

@app.get("/")
async def root():
    return {"status": "ok"}

_http_handler = Mangum(app)


def handler(event, context):
    """Lambda 진입점.

    API Gateway 요청과 EventBridge 스케줄을 같은 함수에서 받는다. 리포트 때문에
    Lambda·IAM 역할·배포 파이프라인을 하나 더 만드는 것보다, 이미 S3 접근 권한과
    코드를 갖춘 이 함수를 재사용하는 편이 관리 지점이 적다.

    EventBridge 이벤트는 `source: aws.events` 로 구분한다. HTTP 요청에는 이 필드가
    없으므로 서로 섞일 일이 없다.
    """
    if isinstance(event, dict) and event.get("source") == "aws.events":
        task = (event.get("detail") or {}).get("task")
        if task == "daily_report":
            from services.daily_report import send_daily_report

            send_daily_report()
            return {"status": "ok", "task": task}
        print(f"[handler] 알 수 없는 예약 작업: {task}")
        return {"status": "ignored", "task": task}

    return _http_handler(event, context)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

