import os
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import firebase_admin
from firebase_admin import auth
from fastapi import Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi_microsoft_identity import initialize, auth_service
import html

from app.core.utils.shared.constants import AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID

security = HTTPBearer()

if os.getenv("AD_ACTIVE") == 1:
    initialize(AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID)
else:
   firebase_admin.initialize_app() 

class FirebaseIdentities(BaseModel):
    microsoft_com: Optional[List[str]] = []
    email: Optional[List[EmailStr]] = []

class FirebaseDetails(BaseModel):
    identities: Optional[FirebaseIdentities]
    sign_in_provider: Optional[str]

class DecodedToken(BaseModel):
    name: Optional[str] = None
    iss: Optional[str] = None
    aud: Optional[str] = None
    auth_time: Optional[int] = None
    user_id: Optional[str] = None
    sub: Optional[str] = None
    iat: Optional[int] = None
    exp: Optional[int] = None
    email: Optional[EmailStr] = None
    email_verified: Optional[bool] = None
    firebase: Optional[FirebaseDetails] = None
    uid: Optional[str] = None

async def get_user(request: Request, token: HTTPAuthorizationCredentials = Depends(security)) -> DecodedToken:
    try:
        jwt = token.credentials
        decoded_token = auth.verify_id_token(jwt)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    return DecodedToken(**decoded_token)

async def get_user_ad(request: Request, token: HTTPAuthorizationCredentials = Depends(security)) -> DecodedToken:
    try:
        token_claims = auth_service.get_token_claims(request)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token_claims

def sanitize_input(input_data: str) -> str:
    input_data = remove_new_lines(input_data)
    return html.escape(input_data)

def remove_new_lines(input_data: str) -> str:
    new_line_pattern = "\\n"
    return input_data.replace(new_line_pattern, "")