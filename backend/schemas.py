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
    store_name: Optional[str] = None
    created_by: Optional[str] = None

class ProductMonitoringCreate(BaseModel):
    barcode: str
    name: str
    price: float
    quantity: int
    total_price: float
    remark: Optional[str] = "" 
    store_name: Optional[str] = None
    created_by: Optional[str] = None

class PurchaseCreate(BaseModel):
    purchase_number: str
    barcode: str
    name: str
    price: float
    quantity: int
    total_price: float
    remark: Optional[str] = ""
    store_name: Optional[str] = None
    created_by: Optional[str] = None

class UserUpdate(BaseModel):
    address: Optional[str] = None
    storename: Optional[str] = None
    storelocation: Optional[str] = None
    password: Optional[str] = None

class MessageCreate(BaseModel):
    receiver_id: int
    content: str

class SukiCreate(BaseModel):
    suki_id: int

class EmployeeCreate(BaseModel):
    employee_id: int
    rank: str

class EmployeeRemove(BaseModel):
    purpose: str

class EmployeeHistoryCreate(BaseModel):
    employee_id: int
    report: Optional[str] = None
    achievement: Optional[str] = None