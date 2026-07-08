"""
Auth endpoints:
  GET /api/auth/me — returns current user info from Firebase token
  GET /api/auth/models — returns available LLM models
"""
from fastapi import APIRouter, Depends

from app.models.models import User
from app.services.llm_client import get_llm_client
from app.utils.firebase_auth import get_current_user, get_optional_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Return current authenticated user."""
    return user.to_dict()


@router.get("/models")
async def list_models(user=Depends(get_optional_user)):
    """List available LLM models (from OpenRouter API)."""
    try:
        client = get_llm_client("groq")
        models = await client.list_models()
        return {"models": models}
    except Exception as e:
        return {
            "models": [
                {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B"},
                {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B"},
                {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 Distill"},
            ],
            "error": str(e),
        }
