from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import httpx
from config import supabase_admin, SUPABASE_URL, SUPABASE_ANON_KEY
from middleware import get_current_user

router = APIRouter()

_PROFILE_FIELDS = (
    "imie, nazwisko, wiek, plec, wzrost, waga, poziom, cel, "
    "dni_treningowe, czas_treningu, miejsce_treningu, dostepny_sprzet, "
    "kontuzje, ograniczenia, jakosc_snu, aktywnosc_codzienna, "
    "poziom_stresu, dieta, osiagniecia, notatki_quiz, "
    "subscription_status, subscription_end_date"
)

_CEL_VALUES = {"masa", "redukcja", "sila", "kondycja"}
_PLEC_VALUES = {"mezczyzna", "kobieta"}
_POZIOM_VALUES = {"poczatkujacy", "srednio", "zaawansowany"}
_CZAS_VALUES = {"30-45", "45-60", "60-90", "90+"}
_MIEJSCE_VALUES = {"silownia", "dom", "mieszanko"}
_SPRZET_VALUES = {"sztanga", "hantle", "lawka_pozioma", "lawka_skosna",
                  "maszyny", "wyciag", "kettlebell", "drazek", "gumy", "brak"}
_SEN_VALUES = {"swietnie", "dobrze", "srednio", "slabo"}
_AKTYWNOSC_VALUES = {"siedzaca", "umiarkowana", "aktywna"}
_STRES_VALUES = {"niski", "umiarkowany", "wysoki", "bardzo_wysoki"}
_DIETA_VALUES = {"nie_pilnuje", "staram_sie", "pilnuje", "specjalna"}


def _verify_password(user_id: str, password: str) -> bool:
    """Weryfikuje hasło przez bezpośrednie wywołanie Supabase Auth REST API."""
    try:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
        email = auth_user.user.email
        res = httpx.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            timeout=10.0,
        )
        return res.status_code == 200
    except Exception:
        return False


def _translate_supabase_error(msg: str) -> str:
    """Tłumaczy angielskie błędy Supabase na polski."""
    m = msg.lower()
    if "already in use" in m or "already registered" in m or "duplicate" in m:
        return "Ten adres email jest już zajęty przez inne konto"
    if "invalid email" in m or "unable to validate email" in m:
        return "Nieprawidłowy format adresu email"
    if "weak password" in m or "password should be" in m:
        return "Hasło jest zbyt słabe — użyj min. 8 znaków"
    if "rate limit" in m or "too many" in m:
        return "Zbyt wiele prób — odczekaj chwilę i spróbuj ponownie"
    if "user not found" in m:
        return "Nie znaleziono użytkownika"
    return "Wystąpił błąd — spróbuj ponownie"


class ProfileUpdateRequest(BaseModel):
    waga: Optional[float] = None
    wzrost: Optional[int] = None
    wiek: Optional[int] = None
    plec: Optional[str] = None
    cel: Optional[str] = None
    poziom: Optional[str] = None
    dni_treningowe: Optional[int] = None
    czas_treningu: Optional[str] = None
    miejsce_treningu: Optional[str] = None
    dostepny_sprzet: Optional[List[str]] = None
    kontuzje: Optional[str] = None
    ograniczenia: Optional[str] = None
    jakosc_snu: Optional[str] = None
    aktywnosc_codzienna: Optional[str] = None
    poziom_stresu: Optional[str] = None
    dieta: Optional[str] = None
    osiagniecia: Optional[str] = None
    notatki_quiz: Optional[str] = None


class EmailUpdateRequest(BaseModel):
    current_password: str
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str


@router.get("/profile")
async def get_profile(user_id: str = Depends(get_current_user)):
    res = supabase_admin.table("user_profiles").select(_PROFILE_FIELDS).eq("user_id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Profil nie znaleziony")
    try:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
        email = auth_user.user.email
    except Exception:
        email = None
    return {**res.data[0], "email": email}


@router.patch("/profile")
async def update_profile(body: ProfileUpdateRequest, user_id: str = Depends(get_current_user)):
    update_data = {}

    if body.waga is not None:
        if not (30 <= body.waga <= 300):
            raise HTTPException(400, "Waga poza zakresem (30–300 kg)")
        update_data["waga"] = body.waga

    if body.wzrost is not None:
        if not (100 <= body.wzrost <= 250):
            raise HTTPException(400, "Wzrost poza zakresem (100–250 cm)")
        update_data["wzrost"] = body.wzrost

    if body.wiek is not None:
        if not (12 <= body.wiek <= 100):
            raise HTTPException(400, "Wiek poza zakresem (12–100)")
        update_data["wiek"] = body.wiek

    if body.plec is not None:
        if body.plec not in _PLEC_VALUES:
            raise HTTPException(400, "Nieprawidłowa płeć")
        update_data["plec"] = body.plec

    if body.cel is not None:
        if body.cel not in _CEL_VALUES:
            raise HTTPException(400, "Nieprawidłowy cel")
        update_data["cel"] = body.cel

    if body.poziom is not None:
        if body.poziom not in _POZIOM_VALUES:
            raise HTTPException(400, "Nieprawidłowy poziom")
        update_data["poziom"] = body.poziom

    if body.dni_treningowe is not None:
        if not (2 <= body.dni_treningowe <= 6):
            raise HTTPException(400, "Dni treningowe poza zakresem (2–6)")
        update_data["dni_treningowe"] = body.dni_treningowe

    if body.czas_treningu is not None:
        if body.czas_treningu not in _CZAS_VALUES:
            raise HTTPException(400, "Nieprawidłowy czas treningu")
        update_data["czas_treningu"] = body.czas_treningu

    if body.miejsce_treningu is not None:
        if body.miejsce_treningu not in _MIEJSCE_VALUES:
            raise HTTPException(400, "Nieprawidłowe miejsce treningu")
        update_data["miejsce_treningu"] = body.miejsce_treningu

    if body.dostepny_sprzet is not None:
        invalid = set(body.dostepny_sprzet) - _SPRZET_VALUES
        if invalid:
            raise HTTPException(400, f"Nieznany sprzęt: {', '.join(invalid)}")
        if not body.dostepny_sprzet:
            raise HTTPException(400, "Wybierz co najmniej jeden sprzęt")
        update_data["dostepny_sprzet"] = body.dostepny_sprzet

    if body.jakosc_snu is not None:
        if body.jakosc_snu not in _SEN_VALUES:
            raise HTTPException(400, "Nieprawidłowa wartość snu")
        update_data["jakosc_snu"] = body.jakosc_snu

    if body.aktywnosc_codzienna is not None:
        if body.aktywnosc_codzienna not in _AKTYWNOSC_VALUES:
            raise HTTPException(400, "Nieprawidłowa aktywność")
        update_data["aktywnosc_codzienna"] = body.aktywnosc_codzienna

    if body.poziom_stresu is not None:
        if body.poziom_stresu not in _STRES_VALUES:
            raise HTTPException(400, "Nieprawidłowy poziom stresu")
        update_data["poziom_stresu"] = body.poziom_stresu

    if body.dieta is not None:
        if body.dieta not in _DIETA_VALUES:
            raise HTTPException(400, "Nieprawidłowa dieta")
        update_data["dieta"] = body.dieta

    # Pola tekstowe — czysczymy pustymi stringami do null; usuwamy null byte (PostgreSQL go odrzuca)
    for field in ("kontuzje", "ograniczenia", "osiagniecia", "notatki_quiz"):
        val = getattr(body, field)
        if val is not None:
            val = val.replace('\x00', '')
            update_data[field] = val.strip() or None

    if not update_data:
        raise HTTPException(400, "Podaj co najmniej jedno pole do zmiany")

    try:
        supabase_admin.table("user_profiles").update(update_data).eq("user_id", user_id).execute()
    except Exception:
        raise HTTPException(500, "Nie udało się zaktualizować profilu — spróbuj ponownie")
    return {"message": "Profil zaktualizowany"}


@router.patch("/email")
async def update_email(body: EmailUpdateRequest, user_id: str = Depends(get_current_user)):
    if not _verify_password(user_id, body.current_password):
        raise HTTPException(401, "Nieprawidłowe hasło")

    # Sprawdź czy nowy email różni się od aktualnego
    try:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
        if auth_user.user.email == body.email:
            raise HTTPException(400, "Podany adres email jest już przypisany do Twojego konta")
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        supabase_admin.auth.admin.update_user_by_id(user_id, {"email": body.email})
        return {
            "message": (
                "Email zmieniony. Od teraz logujesz się nowym adresem. "
                "Twoje dane (historia, plan, profil) zostają bez zmian — "
                "są przypisane do Twojego konta, nie do adresu email."
            )
        }
    except Exception as e:
        raise HTTPException(400, _translate_supabase_error(str(e)))


@router.patch("/password")
async def update_password(body: PasswordUpdateRequest, user_id: str = Depends(get_current_user)):
    if len(body.new_password) < 8:
        raise HTTPException(400, "Nowe hasło musi mieć co najmniej 8 znaków")
    if body.old_password == body.new_password:
        raise HTTPException(400, "Nowe hasło musi być inne niż obecne")
    if not _verify_password(user_id, body.old_password):
        raise HTTPException(401, "Nieprawidłowe obecne hasło")
    try:
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": body.new_password})
        return {"message": "Hasło zmienione"}
    except Exception as e:
        raise HTTPException(400, _translate_supabase_error(str(e)))


@router.delete("/account")
async def delete_account(body: DeleteAccountRequest, user_id: str = Depends(get_current_user)):
    if not _verify_password(user_id, body.password):
        raise HTTPException(401, "Nieprawidłowe hasło")
    try:
        # Usuwamy wszystkie dane użytkownika (RODO — prawo do bycia zapomnianym)
        for table in (
            "plan_history", "training_plans", "profile_changes",
            "pending_conflicts", "conversation_summaries",
            "messages", "conversation_sessions", "user_profiles",
        ):
            supabase_admin.table(table).delete().eq("user_id", user_id).execute()
        supabase_admin.auth.admin.delete_user(user_id)
        return {"message": "Konto usunięte"}
    except Exception as e:
        raise HTTPException(500, str(e))
