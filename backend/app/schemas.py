from pydantic import BaseModel, EmailStr
from typing import Optional


class SignupIn(BaseModel):
    email: EmailStr
    password: str
    shop_name: str = "Tea Stall"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ShopUpdate(BaseModel):
    shop_name: Optional[str] = None


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


class MessageOut(BaseModel):
    message: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    shop_name: str
    qr_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class ItemOut(BaseModel):
    id: int
    name: str
    category: str
    price: float
    image_url: Optional[str] = None

    class Config:
        from_attributes = True
