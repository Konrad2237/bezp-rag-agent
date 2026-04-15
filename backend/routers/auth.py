from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from config import supabase

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(body: RegisterRequest):
    """Rejestracja przez Supabase Auth."""
    try:
        response = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password
        })
        if response.user is None:
            raise HTTPException(status_code=400, detail="Błąd rejestracji")
        return {"message": "Zarejestrowano. Sprawdź email.", "user_id": response.user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(body: LoginRequest):
    """Logowanie przez Supabase Auth — zwraca JWT token."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })
        if response.user is None:
            raise HTTPException(status_code=401, detail="Błędne dane logowania")
        return {
            "access_token": response.session.access_token,
            "user_id": response.user.id
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
