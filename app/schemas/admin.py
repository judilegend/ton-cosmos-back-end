from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict

class LoginPayload(BaseModel):
    email: EmailStr
    password: str
    remember_me:  Optional[bool] = False
    

class ForgotPayload(BaseModel):
    email: EmailStr
    
    
class ResetPayload(BaseModel):
    token: str
    new_password: str
    
    
class UpdatePasswordPayload(BaseModel):
    old_password: str
    new_password: str