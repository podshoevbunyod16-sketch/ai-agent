"""
Firebase Authentication middleware for FastAPI.
Verifies Firebase ID tokens sent in the Authorization: Bearer <token> header.

Setup instructions:
1. Go to https://console.firebase.google.com/ → Create project (or use existing)
2. Project Settings → Service Accounts → Generate new private key
3. Download serviceAccountKey.json
4. Paste its entire content into FIREBASE_SERVICE_ACCOUNT_JSON env var (single-line JSON)
5. Go to Authentication → Sign-in method → Enable: Google, Phone
6. For frontend: Project Settings → General → Your apps → Web app → copy config
"""
import json
import traceback
from datetime import datetime, timezone
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials, exceptions as fb_exceptions
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User

# --- Initialize Firebase Admin SDK (singleton) ---
_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    creds = settings.firebase_credentials_dict
    if creds:
        try:
            firebase_admin.initialize_app(credentials.Certificate(creds))
            _firebase_initialized = True
        except ValueError:
            # Already initialized
            _firebase_initialized = True
        except Exception as e:
            print(f"[FIREBASE] Failed to initialize with service account: {e}")
    else:
        # Try default credentials (e.g., on GCP)
        try:
            firebase_admin.initialize_app()
            _firebase_initialized = True
        except Exception as e:
            print(f"[FIREBASE] No credentials found: {e}")


_init_firebase()

# --- Token verification ---
security = HTTPBearer(auto_error=False)


async def verify_firebase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """
    Verify Firebase ID token from Authorization header.
    Returns decoded token dict or None if no token / invalid.
    """
    if not credentials:
        return None
    if not credentials.scheme.lower() == "bearer":
        return None
    token = credentials.credentials
    if not token:
        return None

    try:
        decoded = auth.verify_id_token(token, clock_skew_seconds=60)
        return decoded
    except fb_exceptions.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token expired. Please re-authenticate.",
        )
    except fb_exceptions.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token revoked.",
        )
    except fb_exceptions.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification error: {str(e)}",
        )


async def get_current_user(
    token_data: Optional[dict] = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: returns the DB User corresponding to the Firebase token.
    Creates the User on first login.
    Raises 401 if no valid token.
    """
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Firebase ID token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_uid = token_data.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing uid claim.",
        )

    # Lookup existing user
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not user:
        # First login — create user record
        email = token_data.get("email") or token_data.get("firebase", {}).get("identities", {}).get("email", [None])[0]
        phone = token_data.get("phone_number")
        name = token_data.get("name") or token_data.get("display_name")
        photo = token_data.get("picture") or token_data.get("photo_url")

        user = User(
            firebase_uid=firebase_uid,
            email=email,
            phone_number=phone,
            display_name=name,
            photo_url=photo,
            created_at=now,
            last_login=now,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update last_login
        user.last_login = now
        await db.commit()
        await db.refresh(user)

    return user


async def get_optional_user(
    token_data: Optional[dict] = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as get_current_user but returns None instead of 401 for public routes."""
    if not token_data:
        return None
    try:
        return await get_current_user(token_data, db)
    except HTTPException:
        return None
