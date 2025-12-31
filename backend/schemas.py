from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    username: str
    password: str

class ProductCreate(BaseModel):
    barcode: str
    name: str
    price: float
    quantity: int

class ProductMonitoringCreate(BaseModel):
    barcode: str
    name: str
    price: float
    quantity: int
    total_price: float
    remark: Optional[str] = "" 