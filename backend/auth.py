from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException, Request, Response, status

from .config import Settings, get_settings
from .db import execute, execute_returning, fetch_one


@dataclass
class AuthenticatedUser:
    user_id: str
    email: str
    organization_id: str
    organization_name: str
    access_token: str | None = None
    refresh_token: str | None = None


class SupabaseAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.supabase_url.rstrip("/")

    async def sign_in(self, email: str, password: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/token?grant_type=password",
                headers={"apikey": self.settings.supabase_anon_key},
                json={"email": email, "password": password},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        return response.json()

    async def sign_up(self, email: str, password: str, metadata: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/auth/v1/signup",
                headers={"apikey": self.settings.supabase_anon_key},
                json={"email": email, "password": password, "data": metadata},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.json().get("msg", "Unable to create account."))
        return response.json()

    async def get_user(self, access_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/auth/v1/user",
                headers={
                    "apikey": self.settings.supabase_anon_key,
                    "Authorization": f"Bearer {access_token}",
                },
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")
        return response.json()


def set_session_cookies(response: Response, access_token: str, refresh_token: str | None) -> None:
    settings = get_settings()
    cookie_kwargs = {
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(settings.session_cookie_name, access_token, **cookie_kwargs)
    if refresh_token:
        response.set_cookie(settings.session_refresh_cookie_name, refresh_token, **cookie_kwargs)


def clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.session_refresh_cookie_name, path="/")


def ensure_membership(user_id: str, email: str, organization_name: str | None = None) -> tuple[str, str]:
    membership = fetch_one(
        """
        select om.organization_id, o.name as organization_name
        from organization_members om
        join organizations o on o.id = om.organization_id
        where om.user_id = %s
        limit 1
        """,
        (user_id,),
    )
    if membership:
        return membership["organization_id"], membership["organization_name"]

    derived_name = organization_name or f"{email.split('@')[0].replace('.', ' ').title()} Organization"
    org = execute_returning(
        """
        insert into organizations (id, name, slug)
        values (%s, %s, %s)
        returning id, name
        """,
        (str(uuid4()), derived_name, f"{email.split('@')[0]}-{uuid4().hex[:8]}"),
    )
    execute(
        """
        insert into organization_members (id, organization_id, user_id, role)
        values (%s, %s, %s, %s)
        """,
        (str(uuid4()), org["id"], user_id, "owner"),
    )
    return org["id"], org["name"]


async def authenticate_request(request: Request) -> AuthenticatedUser:
    settings = get_settings()
    access_token = request.cookies.get(settings.session_cookie_name)
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    auth_client = SupabaseAuthClient(settings)
    user = await auth_client.get_user(access_token)
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email unavailable.")
    organization_id, organization_name = ensure_membership(user["id"], email)
    return AuthenticatedUser(
        user_id=user["id"],
        email=email,
        organization_id=organization_id,
        organization_name=organization_name,
        access_token=access_token,
    )
