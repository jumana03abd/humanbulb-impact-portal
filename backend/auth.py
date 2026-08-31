"""Authentication helpers for the HUMANBULB Impact Portal.

encapsulates Supabase auth calls, allowlist enforcement, and the
organization-membership checks that keep staff scoped to HUMANBULB data.
"""

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
    """Minimal wrapper around the Supabase Auth HTTP API."""

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


def normalize_email(email: str) -> str:
    """Normalize email input so allowlist and membership checks are consistent."""
    return email.strip().lower()


def _allowed_domains(settings: Settings) -> set[str]:
    """Parse the optional fallback staff-domain allowlist from environment settings."""
    return {item.strip().lower() for item in settings.allowed_staff_email_domains.split(",") if item.strip()}


def _allowed_emails(settings: Settings) -> set[str]:
    """Parse the explicit staff-email allowlist used for HUMANBULB portal access."""
    return {normalize_email(item) for item in settings.allowed_staff_emails.split(",") if item.strip()}


def assert_humanbulb_staff_email(email: str) -> None:
    """Reject any sign-in or signup attempt outside the approved staff list."""
    settings = get_settings()
    normalized = normalize_email(email)
    explicit_emails = _allowed_emails(settings)
    domain = normalized.split("@")[-1] if "@" in normalized else ""
    if explicit_emails:
        if normalized in explicit_emails:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only approved HUMANBULB staff accounts can access this portal.",
        )
    if domain in _allowed_domains(settings):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only approved HUMANBULB staff accounts can access this portal.",
    )


def set_session_cookies(response: Response, access_token: str, refresh_token: str | None) -> None:
    """Persist the Supabase session in httpOnly cookies for the static frontend."""
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
    """Remove auth cookies from the browser during logout or session reset."""
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.session_refresh_cookie_name, path="/")


def ensure_membership(user_id: str, email: str) -> tuple[str, str]:
    """Ensure the authenticated user is attached to the configured HUMANBULB org."""
    settings = get_settings()
    assert_humanbulb_staff_email(email)
    membership = fetch_one(
        """
        select om.organization_id, o.name as organization_name
        from organization_members om
        join organizations o on o.id = om.organization_id
        where om.user_id = %s and o.slug = %s
        limit 1
        """,
        (user_id, settings.portal_organization_slug),
    )
    if membership:
        return membership["organization_id"], membership["organization_name"]

    org = fetch_one(
        """
        select id, name
        from organizations
        where slug = %s
        limit 1
        """,
        (settings.portal_organization_slug,),
    )
    if not org:
        org = execute_returning(
            """
            insert into organizations (id, name, slug)
            values (%s, %s, %s)
            returning id, name
            """,
            (str(uuid4()), settings.portal_organization_name, settings.portal_organization_slug),
        )
    execute(
        """
        insert into organization_members (id, organization_id, user_id, role)
        values (%s, %s, %s, %s)
        on conflict (organization_id, user_id) do nothing
        """,
        (str(uuid4()), org["id"], user_id, "owner"),
    )
    return org["id"], org["name"]


async def authenticate_request(request: Request) -> AuthenticatedUser:
    """Resolve the signed-in staff member from the session cookie on each request."""
    settings = get_settings()
    access_token = request.cookies.get(settings.session_cookie_name)
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    auth_client = SupabaseAuthClient(settings)
    user = await auth_client.get_user(access_token)
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email unavailable.")
    assert_humanbulb_staff_email(email)
    organization_id, organization_name = ensure_membership(user["id"], email)
    return AuthenticatedUser(
        user_id=user["id"],
        email=email,
        organization_id=organization_id,
        organization_name=organization_name,
        access_token=access_token,
    )
