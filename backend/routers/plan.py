from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from middleware import get_current_user
from agents.plan_generator import run_plan_generator
from config import supabase

router = APIRouter(prefix="/plan", tags=["plan"])


class GenerateRequest(BaseModel):
    reason: str = "user poprosił o plan"


@router.post("/generate")
def generate_plan(body: GenerateRequest, user_id: str = Depends(get_current_user)):
    result = run_plan_generator(user_id, generation_reason=body.reason)
    if "missing_fields" in result:
        raise HTTPException(status_code=400, detail={
            "missing_fields": result["missing_fields"]
        })
    return result["plan"]


@router.get("/")
def get_plan(user_id: str = Depends(get_current_user)):
    res = supabase.table("training_plans")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Brak planu treningowego")
    return res.data[0]["plan_data"]
