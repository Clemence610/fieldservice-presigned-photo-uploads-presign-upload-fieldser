import asyncio

from fieldservice_uploads.work_order_photos import (
    PhotoUploadRequest,
    WorkOrderPhotoCoordinator,
)


class RecordingSigner:
    def __init__(self) -> None:
        self.key = ""
        self.idempotency_key = ""

    async def presign_photo(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        max_bytes: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.key = key
        self.idempotency_key = idempotency_key
        return {"url": "https://uploads.example/signed-photo"}


def test_follow_up_photo_moves_work_order_to_follow_up_queue() -> None:
    signer = RecordingSigner()
    coordinator = WorkOrderPhotoCoordinator(signer, "work-order-photos")
    request = PhotoUploadRequest(
        work_order_id="WO-2048",
        photo_id="arrival-panel",
        content_type="image/jpeg",
        byte_size=2_400_000,
        dispatch_status="on_site",
        technician_follow_up=True,
    )

    ticket = asyncio.run(coordinator.issue_ticket(request))

    assert ticket.next_status == "awaiting_technician_follow_up"
    assert ticket.method == "PUT"
    assert signer.key == "work-orders/WO-2048/follow-up/arrival-panel"
    assert signer.idempotency_key == "WO-2048:arrival-panel"
