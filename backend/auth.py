from passlib.context import CryptContext

pwd = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd.hash(password)

def verify(password: str, hashed_password: str) -> bool:
    return pwd.verify(password, hashed_password)
