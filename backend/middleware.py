from fastapi import HTTPException, Header, Depends
from config import supabase, supabase_admin


async def get_current_user(authorization: str = Header(...)) -> str:
    """
    Weryfikuje JWT token przez Supabase Auth.
    Token przychodzi w nagłówku: Authorization: Bearer <token>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Nieprawidłowy format tokenu")

    token = authorization.replace("Bearer ", "")

    try:
        response = supabase.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Nieprawidłowy token")
        return response.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")


async def require_active_subscription(user_id: str = Depends(get_current_user)) -> str:
    """Blokuje dostęp jeśli user nie ma aktywnej subskrypcji."""
    res = supabase_admin.table("user_profiles").select("subscription_status").eq("user_id", user_id).execute()
    status = res.data[0].get("subscription_status") if res.data else None
    if status != "active":
        raise HTTPException(status_code=403, detail="Brak aktywnej subskrypcji")
    return user_id
