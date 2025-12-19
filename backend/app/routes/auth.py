from fastapi import APIRouter, HTTPException, Depends
from app.config import supabase
from app.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["Auth"])

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    Verifies the authentication token and returns the user's profile.
    This endpoint is used to confirm that the backend can correctly validate
    tokens issued by Clerk (via Supabase Native Integration).
    """
    return {
        "user_id": user.id,
        "email": user.email,
        "message": "Backend authentication successful"
    }
