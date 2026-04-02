from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegister(BaseModel):
    username: str
    useremail: EmailStr
    password: str
    firstname: str
    middlename: str | None = None
    lastname: str
    address: str
    storename: str
    storelocation: str
    
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

class PurchaseCreate(BaseModel):
    purchase_number: str
    barcode: str
    name: str
    price: float
    quantity: int
    total_price: float
    remark: Optional[str] = ""

class UserUpdate(BaseModel):
    address: Optional[str] = None
    storename: Optional[str] = None
    storelocation: Optional[str] = None
    password: Optional[str] = None

class MessageCreate(BaseModel):
    receiver_id: int
    content: str