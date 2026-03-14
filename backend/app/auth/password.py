from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def _truncate(password: str) -> bytes:
    return password.encode("utf-8")[:72]

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate(password), hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(_truncate(password))