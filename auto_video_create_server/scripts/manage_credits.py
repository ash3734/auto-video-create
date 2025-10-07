import boto3
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

BUCKET_USERS = "blog-to-short-form-users"
BUCKET_CREDITS = "blog-to-short-form-credits"
KEY_USERS = "users.json"

s3 = boto3.client("s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ap-northeast-2"
)

def download_users():
    """사용자 데이터 다운로드"""
    obj = s3.get_object(Bucket=BUCKET_USERS, Key=KEY_USERS)
    return json.loads(obj["Body"].read())

def upload_users(users):
    """사용자 데이터 업로드"""
    s3.put_object(Bucket=BUCKET_USERS, Key=KEY_USERS, Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"))
    print("[S3] users.json 업로드 완료!")

def save_credit_record(credit_record):
    """크레딧 변경 이력 저장"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"credits/{credit_record['user_id']}/{timestamp}.json"
    
    s3.put_object(
        Bucket=BUCKET_CREDITS, 
        Key=key, 
        Body=json.dumps(credit_record, ensure_ascii=False, indent=2).encode("utf-8")
    )
    print(f"[S3] 크레딧 이력 저장 완료: {key}")

def get_credit_history(user_id, limit=50):
    """사용자의 크레딧 변경 이력 조회"""
    try:
        prefix = f"credits/{user_id}/"
        response = s3.list_objects_v2(Bucket=BUCKET_CREDITS, Prefix=prefix)
        
        if 'Contents' not in response:
            return []
        
        # 최신 순으로 정렬
        objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
        objects = objects[:limit]
        
        history = []
        for obj in objects:
            try:
                response = s3.get_object(Bucket=BUCKET_CREDITS, Key=obj['Key'])
                record = json.loads(response['Body'].read())
                history.append(record)
            except Exception as e:
                print(f"이력 조회 오류 {obj['Key']}: {e}")
                continue
        
        return history
    except Exception as e:
        print(f"크레딧 이력 조회 실패: {e}")
        return []

def get_current_credits(user_id):
    """사용자의 현재 크레딧 조회"""
    users = download_users()
    for user in users:
        if user["id"] == user_id:
            return user.get("credits", 0)
    return 0

def add_credits(user_id, amount, reason="admin_add"):
    """크레딧 추가"""
    try:
        users = download_users()
        user_found = False
        
        for user in users:
            if user["id"] == user_id:
                current_credits = user.get("credits", 0)
                new_credits = current_credits + amount
                user["credits"] = new_credits
                user_found = True
                
                # 이력 기록
                credit_record = {
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "change_type": "add",
                    "amount": amount,
                    "reason": reason
                }
                save_credit_record(credit_record)
                
                print(f"[+] {user_id}에게 {amount} 크레딧 추가 완료. 현재 크레딧: {new_credits}")
                break
        
        if not user_found:
            print(f"[!] 사용자 {user_id}를 찾을 수 없습니다.")
            return False
        
        upload_users(users)
        return True
        
    except Exception as e:
        print(f"[!] 크레딧 추가 실패: {e}")
        return False

def deduct_credits(user_id, amount, reason="admin_deduct"):
    """크레딧 차감"""
    try:
        users = download_users()
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
        
        upload_users(users)
        return True
        
    except Exception as e:
        print(f"[!] 크레딧 차감 실패: {e}")
        return False

def set_initial_credits(user_id, amount, reason="initial_setup"):
    """초기 크레딧 설정"""
    try:
        users = download_users()
        user_found = False
        
        for user in users:
            if user["id"] == user_id:
                user["credits"] = amount
                user_found = True
                
                # 이력 기록
                credit_record = {
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "change_type": "initial",
                    "amount": amount,
                    "reason": reason
                }
                save_credit_record(credit_record)
                
                print(f"[*] {user_id} 초기 크레딧 {amount} 설정 완료.")
                break
        
        if not user_found:
            print(f"[!] 사용자 {user_id}를 찾을 수 없습니다.")
            return False
        
        upload_users(users)
        return True
        
    except Exception as e:
        print(f"[!] 초기 크레딧 설정 실패: {e}")
        return False

def list_users_with_credits():
    """크레딧 정보와 함께 사용자 목록 출력"""
    users = download_users()
    print("\n=== 사용자 크레딧 목록 ===")
    for i, user in enumerate(users):
        credits = user.get("credits", 0)
        blog_url = user.get('blog_url', '없음')
        print(f"{i+1}. id: {user['id']}, 크레딧: {credits}, 구독: {user['subscription_start']} ~ {user['subscription_end']}, 블로그: {blog_url}")
    print()

def show_credit_history(user_id):
    """사용자의 크레딧 변경 이력 출력"""
    history = get_credit_history(user_id, 20)
    if not history:
        print(f"[!] {user_id}의 크레딧 이력이 없습니다.")
        return
    
    print(f"\n=== {user_id} 크레딧 변경 이력 (최근 20건) ===")
    for record in history:
        change_type_kr = {"add": "추가", "deduct": "차감", "initial": "초기설정"}.get(record["change_type"], record["change_type"])
        print(f"{record['timestamp']} | {change_type_kr} | {record['amount']:+d} | {record['reason']}")
    print()

def main():
    while True:
        print("\n=== 크레딧 관리 시스템 ===")
        print("1. 사용자 크레딧 목록 보기")
        print("2. 크레딧 추가")
        print("3. 크레딧 차감")
        print("4. 초기 크레딧 설정")
        print("5. 크레딧 이력 보기")
        print("6. 종료")
        
        sel = input("선택: ").strip()
        
        if sel == "1":
            list_users_with_credits()
            
        elif sel == "2":
            user_id = input("사용자 ID: ").strip()
            try:
                amount = int(input("추가할 크레딧: ").strip())
                reason = input("사유 (기본값: admin_add): ").strip() or "admin_add"
                add_credits(user_id, amount, reason)
            except ValueError:
                print("[!] 크레딧은 숫자로 입력해주세요.")
                
        elif sel == "3":
            user_id = input("사용자 ID: ").strip()
            try:
                amount = int(input("차감할 크레딧: ").strip())
                reason = input("사유 (기본값: admin_deduct): ").strip() or "admin_deduct"
                deduct_credits(user_id, amount, reason)
            except ValueError:
                print("[!] 크레딧은 숫자로 입력해주세요.")
                
        elif sel == "4":
            user_id = input("사용자 ID: ").strip()
            try:
                amount = int(input("설정할 초기 크레딧: ").strip())
                reason = input("사유 (기본값: initial_setup): ").strip() or "initial_setup"
                set_initial_credits(user_id, amount, reason)
            except ValueError:
                print("[!] 크레딧은 숫자로 입력해주세요.")
                
        elif sel == "5":
            user_id = input("사용자 ID: ").strip()
            show_credit_history(user_id)
            
        elif sel == "6":
            print("종료합니다.")
            break
            
        else:
            print("잘못된 입력입니다.")

if __name__ == "__main__":
    main()
