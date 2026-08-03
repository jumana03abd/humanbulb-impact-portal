from pathlib import Path
from urllib.parse import quote

import httpx

from .config import Settings, get_settings


class StorageClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.supabase_url.rstrip("/")

    async def upload_bytes(self, bucket: str, path: str, content: bytes, content_type: str) -> None:
        encoded_path = "/".join(quote(part, safe="") for part in Path(path).parts)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/storage/v1/object/{bucket}/{encoded_path}",
                headers={
                    "apikey": self.settings.supabase_service_role_key,
                    "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=content,
            )
        response.raise_for_status()

    async def download_bytes(self, bucket: str, path: str) -> bytes:
        encoded_path = "/".join(quote(part, safe="") for part in Path(path).parts)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base_url}/storage/v1/object/{bucket}/{encoded_path}",
                headers={
                    "apikey": self.settings.supabase_service_role_key,
                    "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
                },
            )
        response.raise_for_status()
        return response.content

    async def delete_object(self, bucket: str, path: str) -> None:
        encoded_path = "/".join(quote(part, safe="") for part in Path(path).parts)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.delete(
                f"{self.base_url}/storage/v1/object/{bucket}/{encoded_path}",
                headers={
                    "apikey": self.settings.supabase_service_role_key,
                    "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
                },
            )
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
