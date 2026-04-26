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

        return {"message": "Konto założone! Wysłaliśmy link aktywacyjny na Twój email — potwierdź go przed pierwszym logowaniem."}
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
        if "email not confirmed" in msg:
            raise HTTPException(
                status_code=401,
                detail="Email nie został potwierdzony — sprawdź skrzynkę i kliknij link aktywacyjny",
            )
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
    """Sprawdza profil i status subskrypcji zalogowanego usera.
    Jeśli subskrypcja nie jest aktywna — sprawdza pending_subscriptions po emailu
    (flow: Stripe → rejestracja — user płaci przed założeniem konta).
    """
    from config import supabase_admin as _admin
    response = supabase.table("user_profiles").select("quiz_completed, subscription_status").eq("user_id", user_id).execute()
    row = response.data[0] if response.data else {}
    has_profile = row.get("quiz_completed") is True
    subscription_status = row.get("subscription_status")

    if subscription_status != "active":
        try:
            auth_user = _admin.auth.admin.get_user_by_id(user_id)
            email = auth_user.user.email.lower() if auth_user.user else None
            if email:
                pending = _admin.table("pending_subscriptions").select("*").eq("email", email).execute()
                if pending.data:
                    ps = pending.data[0]
                    _admin.table("user_profiles").update({
                        "subscription_status": "active",
                        "subscription_end_date": ps.get("subscription_end_date"),
                        "stripe_customer_id": ps.get("stripe_customer_id"),
                    }).eq("user_id", user_id).execute()
                    _admin.table("pending_subscriptions").delete().eq("email", email).execute()
                    subscription_status = "active"
        except Exception:
            pass

    return {"user_id": user_id, "has_profile": has_profile, "subscription_status": subscription_status}
