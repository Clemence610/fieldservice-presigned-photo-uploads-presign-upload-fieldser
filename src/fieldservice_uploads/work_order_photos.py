from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class DispatchStatus(StrEnum):
    DISPATCHED = "dispatched"
    ON_SITE = "on_site"
    COMPLETED = "completed"


@dataclass
class PhotoUploadRequest:
    work_order_id: str
    photo_id: str
    content_type: str
    byte_size: int
    dispatch_status: DispatchStatus
    technician_follow_up: bool

    def __post_init__(self) -> None:
        identifier = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
        if not identifier.fullmatch(self.work_order_id):
            raise ValueError("work_order_id must be 3-64 letters, digits, '_' or '-'")
        if not identifier.fullmatch(self.photo_id):
            raise ValueError("photo_id must be 3-64 letters, digits, '_' or '-'")
        if self.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("content_type must be image/jpeg, image/png or image/webp")
        if not isinstance(self.byte_size, int) or not 0 < self.byte_size <= 10_000_000:
            raise ValueError("byte_size must be an integer from 1 through 10000000")
        self.dispatch_status = DispatchStatus(self.dispatch_status)


@dataclass
class PhotoUploadTicket:
    upload_url: str
    method: str
    object_key: str
    next_status: str


class PhotoSigner(Protocol):
    async def presign_photo(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        max_bytes: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        raise AssertionError("Protocol method has no runtime implementation")


class WorkOrderPhotoCoordinator:
    def __init__(self, signer: PhotoSigner, bucket: str) -> None:
        self.signer = signer
        self.bucket = bucket

    async def issue_ticket(self, request: PhotoUploadRequest) -> PhotoUploadTicket:
        queue = "follow-up" if request.technician_follow_up else "dispatch"
        object_key = (
            f"work-orders/{request.work_order_id}/{queue}/{request.photo_id}"
        )
        signed = await self.signer.presign_photo(
            self.bucket,
            object_key,
            content_type=request.content_type,
            max_bytes=request.byte_size,
            idempotency_key=f"{request.work_order_id}:{request.photo_id}",
        )
        next_status = (
            "awaiting_technician_follow_up"
            if request.technician_follow_up
            else request.dispatch_status.value
        )
        return PhotoUploadTicket(
            upload_url=str(signed["url"]),
            method="PUT",
            object_key=object_key,
            next_status=next_status,
        )
