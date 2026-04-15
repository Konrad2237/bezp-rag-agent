from fastapi import HTTPException, Header
from config import supabase


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
