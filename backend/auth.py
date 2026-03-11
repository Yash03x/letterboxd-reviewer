"""
Clerk JWT verification dependency for FastAPI.

Usage:
    from auth import get_current_user, ClerkUser

    @app.get("/protected")
    async def protected_route(user: ClerkUser = Depends(get_current_user)):
        return {"user_id": user.user_id}
"""

import os
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dataclasses import dataclass
import jwt
from jwt import PyJWKClient

CLERK_JWKS_URL = os.environ.get(
    "CLERK_JWKS_URL",
    # Fallback: set CLERK_FRONTEND_API in env, e.g. https://your-clerk-domain.clerk.accounts.dev
    f"{os.environ.get('CLERK_FRONTEND_API', '')}/.well-known/jwks.json",
)

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:
    return PyJWKClient(CLERK_JWKS_URL, cache_keys=True)


@dataclass
class ClerkUser:
    user_id: str
    session_id: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ClerkUser:
    """Extract and verify Clerk JWT from Authorization: Bearer <token> header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    return ClerkUser(user_id=user_id, session_id=session_id)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ClerkUser | None:
    """Same as get_current_user but returns None instead of raising for public routes."""
    if credentials is None:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
