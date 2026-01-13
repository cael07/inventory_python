from passlib.context import CryptContext
import hashlib

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Safe password hashing:
    - Supports any password length
    - Prevents bcrypt 72-byte error
    - Guards against double hashing
    """

    # If already bcrypt-hashed, return as-is
    if password.startswith("$2a$") or password.startswith("$2b$"):
        return password

    sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd.hash(sha)

def verify(password: str, hashed_password: str) -> bool:
    sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd.verify(sha, hashed_password)
