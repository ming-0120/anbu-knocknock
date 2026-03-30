from passlib.context import CryptContext
import bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def verify_password(password: str, hashed: str) -> bool:
    """
    평문 비밀번호와 해시된 비밀번호를 비교합니다.
    """
    try:
        # bcrypt는 내부적으로 72바이트까지만 인식하므로 안전하게 바이트로 변환 후 자릅니다.
        password_bytes = password.encode('utf-8')[:72]
        hashed_bytes = hashed.encode('utf-8')
        
        # 해시값 비교 수행
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        print(f"비밀번호 검증 중 에러: {e}")
        return False

def hash_password(password: str) -> str:
    """
    비밀번호를 bcrypt 알고리즘으로 해싱합니다.
    """
    # 1. 바이트 변환 및 72바이트 제한 적용
    password_bytes = password.encode('utf-8')[:72]
    
    # 2. 솔트(Salt) 생성 및 해싱
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # 3. DB 저장을 위해 문자열로 디코딩하여 반환
    return hashed.decode('utf-8')