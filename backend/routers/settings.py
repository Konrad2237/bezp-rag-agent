from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from config import supabase_admin
from middleware import get_current_user

router = APIRouter()


class ProfileUpdateRequest(BaseModel):
    waga: Optional[float] = None
    cel: Optional[str] = None


class EmailUpdateRequest(BaseModel):
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    password: str


@router.get("/profile")
async def get_profile(user_id: str = Depends(get_current_user)):
    """Zwraca pola profilu edytowalne w ustawieniach."""
    res = supabase_admin.table("user_profiles").select("waga, cel").eq("user_id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Profil nie znaleziony")
    return res.data[0]


@router.patch("/profile")
async def update_profile(body: ProfileUpdateRequest, user_id: str = Depends(get_current_user)):
    """Aktualizuje wagę i/lub cel treningowy."""
    if body.waga is None and body.cel is None:
        raise HTTPException(status_code=400, detail="Podaj co najmniej jedno pole do zmiany")

    if body.waga is not None and not (30 <= body.waga <= 300):
        raise HTTPException(status_code=400, detail="Waga poza zakresem (30-300)")

    if body.cel is not None and body.cel not in ["masa", "redukcja", "sila", "kondycja"]:
        raise HTTPException(status_code=400, detail="Nieprawidłowy cel")

    update_data = {}
    if body.waga is not None:
        update_data["waga"] = body.waga
    if body.cel is not None:
        update_data["cel"] = body.cel

    supabase_admin.table("user_profiles").update(update_data).eq("user_id", user_id).execute()
    return {"message": "Profil zaktualizowany"}


@router.patch("/email")
async def update_email(body: EmailUpdateRequest, user_id: str = Depends(get_current_user)):
    """Zmienia adres email konta."""
    try:
        supabase_admin.auth.admin.update_user_by_id(user_id, {"email": body.email})
        return {"message": "Email zaktualizowany"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/password")
async def update_password(body: PasswordUpdateRequest, user_id: str = Depends(get_current_user)):
    """Zmienia hasło konta."""
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Hasło musi mieć co najmniej 8 znaków")
    try:
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": body.password})
        return {"message": "Hasło zaktualizowane"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/account")
async def delete_account(user_id: str = Depends(get_current_user)):
    """Usuwa konto i wszystkie dane użytkownika."""
    try:
        # Usuń profil (cascade usunie powiązane dane jeśli FK skonfigurowane)
        supabase_admin.table("user_profiles").delete().eq("user_id", user_id).execute()
        # Usuń konto auth
        supabase_admin.auth.admin.delete_user(user_id)
        return {"message": "Konto usunięte"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
