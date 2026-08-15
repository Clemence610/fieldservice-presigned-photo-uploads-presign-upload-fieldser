from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .infrai_storage import InfraiError, InfraiStorage
from .work_order_photos import (
    PhotoUploadRequest,
    PhotoUploadTicket,
    WorkOrderPhotoCoordinator,
)

BUCKET = os.environ.get("WORK_ORDER_PHOTO_BUCKET", "fieldservice-work-order-photos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = InfraiStorage()
    await storage.create_bucket(BUCKET)
    app.state.coordinator = WorkOrderPhotoCoordinator(storage, BUCKET)
    yield
    await storage.close()


service = FastAPI(title="Field-service photo uploads", lifespan=lifespan)


@service.post("/work-orders/photo-upload", response_model=PhotoUploadTicket)
async def request_photo_upload(request: PhotoUploadRequest) -> PhotoUploadTicket:
    coordinator: WorkOrderPhotoCoordinator = service.state.coordinator
    try:
        return await coordinator.issue_ticket(request)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

