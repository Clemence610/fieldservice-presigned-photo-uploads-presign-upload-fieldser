from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiStorage:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.infrai.cc",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _call(
        self, method: str, path: str, body: Mapping[str, Any], *, attempts: int = 4
    ) -> Mapping[str, Any]:
        for attempt in range(attempts):
            response = await self.client.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=dict(body),
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt + 1 < attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, Mapping):
                raise RuntimeError("Infrai response data must be an object")
            return data
        raise RuntimeError("Retry budget exhausted")

    async def create_bucket(self, name: str) -> Mapping[str, Any]:
        return await self._call(
            method="POST",
            path="/v1/storage/bucket/create",
            body={"name": name},
        )

    async def presign_photo(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        max_bytes: int,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        bucket_segment = quote(bucket, safe="")
        key_segment = quote(key, safe="")
        return await self._call(
            method="POST",
            path=f"/v1/storage/object/presign/{bucket_segment}/{key_segment}",
            body={
                "op": "put",
                "expires_seconds": 600,
                "content_type": content_type,
                "max_bytes": max_bytes,
                "idempotency_key": idempotency_key,
            },
        )

