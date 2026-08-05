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

def _unlimited_status(user):
    """무제한 플랜 상태 문자열. (BE is_unlimited_active 와 동일 규칙)"""
    start, end = user.get("unlimited_start"), user.get("unlimited_end")
    if not start or not end:
        return "-"
    try:
        today = datetime.utcnow().date()
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return "형식오류"
    if today < s:
        return f"예정({start}~{end})"
    if today > e:
        return f"만료({end})"
    return f"무제한중(~{end})"


def set_unlimited_plan(user_id, start, end):
    """무제한 플랜 기간 설정. 기간 중에는 크레딧 차감 없이 무제한 생성."""
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        print("[!] 날짜는 YYYY-MM-DD 형식으로 입력해주세요.")
        return
    if e < s:
        print("[!] 종료일이 시작일보다 빠릅니다.")
        return

    users = download_users()
    for user in users:
        if user["id"] == user_id:
            user["unlimited_start"] = start
            user["unlimited_end"] = end
            upload_users(users)
            print(f"[*] {user_id} 무제한 플랜 설정: {start} ~ {end}")
            # 구독 기간과는 별도 관리 — 구독이 만료돼 있으면 로그인 자체가 막히므로 경고만 한다.
            sub_end = user.get("subscription_end")
            try:
                if sub_end and datetime.strptime(sub_end, "%Y-%m-%d").date() < e:
                    print(f"[!] 주의: 구독 종료일({sub_end})이 무제한 종료일({end})보다 빠릅니다.")
                    print("    구독이 만료되면 로그인 자체가 막혀 무제한도 쓸 수 없습니다.")
                    print("    edit_users_json.py 의 '4. 구독일 변경' 으로 구독 기간을 함께 늘려주세요.")
            except ValueError:
                pass
            save_credit_record({
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "change_type": "unlimited_set",
                "amount": 0,
                "reason": f"unlimited_plan {start}~{end}",
            })
            return
    print(f"[!] 사용자 {user_id}를 찾을 수 없습니다.")


def clear_unlimited_plan(user_id):
    """무제한 플랜 해제 (일반 크레딧 정책으로 복귀)."""
    users = download_users()
    for user in users:
        if user["id"] == user_id:
            if not user.get("unlimited_start") and not user.get("unlimited_end"):
                print(f"[!] {user_id}는 무제한 플랜이 설정돼 있지 않습니다.")
                return
            user.pop("unlimited_start", None)
            user.pop("unlimited_end", None)
            upload_users(users)
            print(f"[*] {user_id} 무제한 플랜 해제 완료. 이후 크레딧 차감 정상 적용.")
            save_credit_record({
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "change_type": "unlimited_clear",
                "amount": 0,
                "reason": "unlimited_plan cleared",
            })
            return
    print(f"[!] 사용자 {user_id}를 찾을 수 없습니다.")


def list_users_with_credits():
    """크레딧 정보와 함께 사용자 목록 출력"""
    users = download_users()
    print("\n=== 사용자 크레딧 목록 ===")
    for i, user in enumerate(users):
        credits = user.get("credits", 0)
        blog_url = user.get('blog_url', '없음')
        unlimited = _unlimited_status(user)
        print(f"{i+1}. id: {user['id']}, 크레딧: {credits}, 무제한: {unlimited}, 구독: {user['subscription_start']} ~ {user['subscription_end']}, 블로그: {blog_url}")
    print()

def show_credit_history(user_id):
    """사용자의 크레딧 변경 이력 출력"""
    history = get_credit_history(user_id, 20)
    if not history:
        print(f"[!] {user_id}의 크레딧 이력이 없습니다.")
        return
    
    print(f"\n=== {user_id} 크레딧 변경 이력 (최근 20건) ===")
    for record in history:
        change_type_kr = {
            "add": "추가", "deduct": "차감", "initial": "초기설정",
            "unlimited_use": "무제한사용", "unlimited_set": "무제한설정", "unlimited_clear": "무제한해제",
        }.get(record["change_type"], record["change_type"])
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
        print("6. 무제한 플랜 설정 (기간 중 차감 없이 무제한 생성)")
        print("7. 무제한 플랜 해제")
        print("8. 종료")
        
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
            user_id = input("사용자 ID: ").strip()
            start = input("무제한 시작일(YYYY-MM-DD): ").strip()
            end = input("무제한 종료일(YYYY-MM-DD): ").strip()
            set_unlimited_plan(user_id, start, end)

        elif sel == "7":
            user_id = input("사용자 ID: ").strip()
            clear_unlimited_plan(user_id)

        elif sel == "8":
            print("종료합니다.")
            break
            
        else:
            print("잘못된 입력입니다.")

if __name__ == "__main__":
    main()
