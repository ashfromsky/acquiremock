import secrets
import string
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_secure_otp(length: int = 4) -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)

def hash_sensitive_data(data: str) -> str:
    return pwd_context.hash(data)

def verify_sensitive_data(plain_data: str, hashed_data: str) -> bool:
    return pwd_context.verify(plain_data, hashed_data)