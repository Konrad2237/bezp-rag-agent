from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from config import supabase, supabase_admin
from middleware import get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    imie: str
    nazwisko: str


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

        # Jeśli user już istnieje, Supabase zwraca go bez sesji i bez tożsamości
        if not response.user.identities:
            raise HTTPException(status_code=400, detail="Konto z tym adresem email już istnieje.")

        supabase_admin.table("user_profiles").insert({
            "user_id": response.user.id,
            "imie": body.imie,
            "nazwisko": body.nazwisko,
            "quiz_completed": False,
        }).execute()

        return {"message": "Konto założone!"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[REGISTER ERROR] {type(e).__name__}: {e}")
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
            "refresh_token": response.session.refresh_token,
            "user_id": response.user.id
        }
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "invalid login credentials" in msg or "invalid email or password" in msg:
            raise HTTPException(status_code=401, detail="Błędny email lub hasło")
        raise HTTPException(status_code=401, detail="Błąd logowania — spróbuj ponownie")


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    """Odnawia wygasły JWT token używając refresh_token."""
    try:
        response = supabase.auth.refresh_session(body.refresh_token)
        if response.session is None:
            raise HTTPException(status_code=401, detail="Sesja wygasła — zaloguj się ponownie")
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    """Sprawdza profil i status subskrypcji zalogowanego usera."""
    response = supabase_admin.table("user_profiles").select("quiz_completed, subscription_status").eq("user_id", user_id).execute()
    row = response.data[0] if response.data else {}
    has_profile = row.get("quiz_completed") is True
    subscription_status = row.get("subscription_status")

    return {"user_id": user_id, "has_profile": has_profile, "subscription_status": subscription_status}
