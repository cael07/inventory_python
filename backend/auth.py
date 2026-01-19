import os
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta

# -------------------------
# PASSWORD HASHING (UNCHANGED)
# -------------------------
pwd = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd.hash(password)

def verify(password: str, hashed_password: str) -> bool:
    return pwd.verify(password, hashed_password)

# -------------------------
# JWT SETTINGS (ENV-BASED)
# -------------------------
SECRET_KEY = os.getenv("JWT_SECRET")   # 👈 THIS ONE
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET environment variable not set")

# -------------------------
# JWT HELPERS
# -------------------------
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
