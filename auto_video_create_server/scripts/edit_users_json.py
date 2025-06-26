import boto3
import json
import os
from datetime import datetime

BUCKET = "blog-to-short-form-users"
KEY = "users.json"

s3 = boto3.client("s3",
    aws_access_key_id="xxxxxxx",
    aws_secret_access_key="xxxxxxx",
    region_name="ap-northeast-2"
)

def download_users():
    obj = s3.get_object(Bucket=BUCKET, Key=KEY)
    return json.loads(obj["Body"].read())

def upload_users(users):
    s3.put_object(Bucket=BUCKET, Key=KEY, Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"))
    print("[S3] users.json 업로드 완료!")

def print_users(users):
    print("\n=== 사용자 목록 ===")
    for i, user in enumerate(users):
        print(f"{i+1}. id: {user['id']}, pw: {user['pw']}, 구독: {user['subscription_start']} ~ {user['subscription_end']}")
    print()

def add_user(users):
    id = input("새 id: ").strip()
    pw = input("비밀번호: ").strip()
    start = input("구독 시작일(YYYY-MM-DD): ").strip()
    end = input("구독 종료일(YYYY-MM-DD): ").strip()
    users.append({"id": id, "pw": pw, "subscription_start": start, "subscription_end": end})
    print(f"[+] 사용자 {id} 추가 완료.")

def delete_user(users):
    id = input("삭제할 id: ").strip()
    before = len(users)
    users[:] = [u for u in users if u["id"] != id]
    if len(users) < before:
        print(f"[-] 사용자 {id} 삭제 완료.")
    else:
        print(f"[!] 해당 id 없음.")

def update_subscription(users):
    id = input("구독일 변경할 id: ").strip()
    for user in users:
        if user["id"] == id:
            start = input(f"새 구독 시작일(YYYY-MM-DD, 현재: {user['subscription_start']}): ").strip()
            end = input(f"새 구독 종료일(YYYY-MM-DD, 현재: {user['subscription_end']}): ").strip()
            user["subscription_start"] = start
            user["subscription_end"] = end
            print(f"[*] {id} 구독일 변경 완료.")
            return
    print(f"[!] 해당 id 없음.")

def main():
    users = download_users()
    while True:
        print("\n1. 전체 목록 보기\n2. 사용자 추가\n3. 사용자 삭제\n4. 구독일 변경\n5. 저장(업로드)\n6. 종료")
        sel = input("선택: ").strip()
        if sel == "1":
            print_users(users)
        elif sel == "2":
            add_user(users)
        elif sel == "3":
            delete_user(users)
        elif sel == "4":
            update_subscription(users)
        elif sel == "5":
            upload_users(users)
        elif sel == "6":
            print("종료합니다.")
            break
        else:
            print("잘못된 입력입니다.")

if __name__ == "__main__":
    main() 