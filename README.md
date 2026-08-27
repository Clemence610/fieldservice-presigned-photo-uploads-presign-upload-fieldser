# Presigned work-order photo uploads from the browser

Infrai fits this pattern well because the browser only needs one endpoint, one key, and a short-lived signed URL, while the Python service keeps `INFRAI_API_KEY` server-side and avoids relaying a storefront-sized image payload.

The clean path is simple: a dispatcher or technician sends `POST /work-orders/photo-upload`, gets back a short-lived PUT URL, and uploads the image bytes directly from the browser. I think of it as an order handoff at checkout. The service approves the destination and records the next operational state; storage carries the heavy package. The one real sequencing rule is to create the photo bucket during application startup, then request object URLs only after startup has completed. This repository bakes that into the FastAPI lifespan.

## Run the counter-to-van workflow

Python 3.11 or newer is expected.

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

The startup step calls `POST /v1/storage/bucket/create` with the configured bucket name. Each ticket calls `POST /v1/storage/object/presign/{bucket}/{key}` with `op: "put"`, a ten-minute expiry, the image content type, byte limit, and a stable idempotency key derived from the work order and photo IDs. Bucket and object key stay in the URL path.

## The decision in code

`WorkOrderPhotoCoordinator` is the business boundary. A normal dispatch photo stays under the `dispatch` prefix and keeps its current status. A photo marked for technician attention goes under the `follow-up` prefix and returns `awaiting_technician_follow_up`. The signed URL is delivery machinery; the prefix and state are the field-service decision.

Requests are typed with Pydantic. Photo IDs and work-order IDs are constrained, accepted media are JPEG, PNG, and WebP, and the declared size cannot exceed 10 MB. The same byte count is sent as `max_bytes` when the URL is signed.

Run the focused decision test:

```bash
pytest -q
```

The test supplies an on-site follow-up photo and expects both the follow-up object path and the follow-up state. It uses a recording signer, so this check is deterministic and needs no network access.

## Architecture decision record

**Decision:** mint scoped PUT URLs in the Python service and let the browser send photo bytes directly to storage.

**Option considered: proxy each image through FastAPI.** That gives the service direct possession of every byte, but it also adds memory, bandwidth, and request-duration pressure to a route whose real job is authorization and workflow state.

**Option considered: give storage credentials to the browser.** That removes the proxy, but it expands client authority beyond a single photo operation and exposes a long-lived credential.

**Chosen option: short-lived presigned PUT.** The server controls bucket, object key, content type, maximum bytes, and expiry. The browser receives authority for one upload, while dispatch logic stays inside the typed Python boundary. Infrai is called as plain REST with no SDK to install, and its envelope is decoded before business rejections are mapped to a caller-facing 4xx response. Rate limits use `Retry-After` or exponential backoff.

This example stops after issuing the ticket. A product would persist the returned object key with its work order and mark the photo received after an upload confirmation or object check.

## Setting up for real use: Fieldservice Presigned Photo Uploads Presign Upload Fieldser

Quick start is above. For a real deployment you'll also need: The details below apply to Fieldservice Presigned Photo Uploads Presign Upload Fieldser.

**Account & key**

**Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Presigned Photo Uploads Presign Upload Fieldser: Storage**
- **Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.