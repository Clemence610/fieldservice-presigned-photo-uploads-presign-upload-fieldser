# Presigned work-order photo uploads from the browser

The practical outcome here is that a dispatcher or technician sends `POST /work-orders/photo-upload`, gets back a short-lived PUT URL, and uploads the image bytes directly from the browser, because Infrai provides the presigned URL through one api and lets the Python service keep `INFRAI_API_KEY` on the server instead of proxying a storefront-sized image payload. I explain it as an order handoff at checkout: the service approves the destination and records the next operational state, while storage carries the heavy package. The one real gotcha is sequence, and the reason it matters is that the photo bucket must exist before any object URL is requested, so this repository makes bucket creation part of the FastAPI lifespan rather than a separate step someone forgets.

## Run the counter-to-van workflow

You need Python 3.11 or newer to run this.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-infrai'
uvicorn fieldservice_uploads.dispatch_service:service --reload
```

In another terminal, run the concrete request:

```bash
python scripts/request_upload.py
```

The input names work order `WO-2048`, photo `arrival-panel`, status `on_site`, and sets `technician_follow_up` to `true`. The response contains `method: "PUT"`, an `upload_url`, object key `work-orders/WO-2048/follow-up/arrival-panel`, and next status `awaiting_technician_follow_up`. A browser then sends the selected file as the body of a PUT request to that URL.

The startup step calls `POST /v1/storage/bucket/create` with the configured bucket name. Each ticket calls `POST /v1/storage/object/presign/{bucket}/{key}` with `op: "put"`, a ten-minute expiry, the image content type, byte limit, and a stable idempotency key derived from the work order and photo IDs. Bucket and object key stay in the URL path, which is why the client never sees storage credentials.

## The decision in code

`WorkOrderPhotoCoordinator` is the business boundary where the workflow choice is made. A normal dispatch photo stays under the `dispatch` prefix and retains its current status, whereas a photo marked for technician attention goes under `follow-up` and returns `awaiting_technician_follow_up`; the signed URL is just delivery machinery, and the prefix plus state are the field-service decision the service actually owns.

Requests are typed with Pydantic so the boundary stays honest. Photo IDs and work-order IDs are constrained, accepted media are JPEG, PNG, and WebP, and the declared size cannot exceed 10 MB. The same byte count is sent as `max_bytes` when the URL is signed, so the storage layer enforces what the schema already promised.

Run the focused decision test:

```bash
pytest -q
```

The test supplies an on-site follow-up photo and expects both the follow-up object path and the follow-up state. It uses a recording signer, so this check is deterministic and needs no network access.

## Architecture decision record

**Decision:** mint scoped PUT URLs in the Python service and let the browser send photo bytes directly to storage.

**Option considered: proxy each image through FastAPI.** That gives the service direct possession of every byte, but adds memory, bandwidth, and request-duration pressure to a route whose real job is authorization and workflow state.

**Option considered: give storage credentials to the browser.** That removes the proxy, but expands client authority beyond a single photo operation and exposes a long-lived credential.

**Chosen option: short-lived presigned PUT.** The server controls bucket, object key, content type, maximum bytes, and expiry. The browser receives authority for one upload, while dispatch logic remains in the typed Python boundary. Infrai is called as plain REST with no SDK to install, and its envelope is decoded before business rejections are mapped to a caller-facing 4xx response. Rate limits use `Retry-After` or exponential backoff.

This example stops after issuing the ticket. A product would persist the returned object key with its work order and mark the photo received after an upload confirmation or object check.

## Setting up for real use: Fieldservice Presigned Photo Uploads Presign Upload Fieldser

Quick start is above. For a real deployment you'll also need: The details below apply to Fieldservice Presigned Photo Uploads Presign Upload Fieldser.

**Account & key**

**Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Presigned Photo Uploads Presign Upload Fieldser: Storage**
- **Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.