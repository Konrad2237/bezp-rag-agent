from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from middleware import get_current_user
from config import supabase, supabase_admin

router = APIRouter()


class QuizRequest(BaseModel):
    wiek: int
    plec: str
    wzrost: int
    waga: float
    poziom: str
    cel: str
    dni_treningowe: int
    czas_treningu: str
    miejsce_treningu: str
    dostepny_sprzet: List[str]
    kontuzje: Optional[str] = None
    ograniczenia: Optional[str] = None
    jakosc_snu: Optional[str] = None
    aktywnosc_codzienna: Optional[str] = None
    poziom_stresu: Optional[str] = None
    dieta: Optional[str] = None
    osiagniecia: Optional[str] = None
    notatki_quiz: Optional[str] = None


@router.post("/submit")
async def submit_quiz(
    body: QuizRequest,
    user_id: str = Depends(get_current_user)
):
    """Zapisuje wyniki quizu do user_profiles."""

    # Walidacja zakresów
    if not (12 <= body.wiek <= 100):
        raise HTTPException(status_code=400, detail="Wiek poza zakresem (12-100)")
    if not (100 <= body.wzrost <= 250):
        raise HTTPException(status_code=400, detail="Wzrost poza zakresem (100-250)")
    if not (30 <= body.waga <= 300):
        raise HTTPException(status_code=400, detail="Waga poza zakresem (30-300)")
    if body.plec not in ["mezczyzna", "kobieta"]:
        raise HTTPException(status_code=400, detail="Nieprawidłowa płeć")
    if body.cel not in ["masa", "redukcja", "sila", "kondycja"]:
        raise HTTPException(status_code=400, detail="Nieprawidłowy cel")
    if body.poziom not in ["poczatkujacy", "srednio", "zaawansowany"]:
        raise HTTPException(status_code=400, detail="Nieprawidłowy poziom")
    if not (2 <= body.dni_treningowe <= 6):
        raise HTTPException(status_code=400, detail="Dni treningowe poza zakresem (2-6)")
    if not body.dostepny_sprzet:
        raise HTTPException(status_code=400, detail="Wybierz co najmniej jeden sprzęt")

    try:
        supabase_admin.table("user_profiles").upsert({
            "user_id": user_id,
            "wiek": body.wiek,
            "plec": body.plec,
            "wzrost": body.wzrost,
            "waga": body.waga,
            "poziom": body.poziom,
            "cel": body.cel,
            "dni_treningowe": body.dni_treningowe,
            "czas_treningu": body.czas_treningu,
            "miejsce_treningu": body.miejsce_treningu,
            "dostepny_sprzet": body.dostepny_sprzet,
            "kontuzje": body.kontuzje,
            "ograniczenia": body.ograniczenia,
            "jakosc_snu": body.jakosc_snu,
            "aktywnosc_codzienna": body.aktywnosc_codzienna,
            "poziom_stresu": body.poziom_stresu,
            "dieta": body.dieta,
            "osiagniecia": body.osiagniecia,
            "notatki_quiz": body.notatki_quiz,
            "quiz_completed": True,
        }, on_conflict="user_id").execute()

        return {"message": "Quiz zapisany. Możesz zacząć rozmowę z agentem."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
