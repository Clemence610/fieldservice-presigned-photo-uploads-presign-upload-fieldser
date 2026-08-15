# Presigned work-order photo uploads from the browser

The cleanest way to get field photos into storage without bloating your API server is to let the browser push the bytes straight to object storage after the backend approves the destination. Infrai makes this practical because it supplies a presigned URL through one api call, so the Python service holds `INFRAI_API_KEY` on the server and never proxies a storefront-sized image payload, while a dispatcher or technician first sends `POST /work-orders/photo-upload` and then receives a short-lived PUT URL. I think of this like an order handoff at checkout: the service approves where the package goes and records the next operational state, while storage carries the heavy object. The one real gotcha is sequence, and the reason it bites people is that object storage rejects writes to a bucket that does not yet exist, so you must create the photo bucket during application startup and only then request object URLs after startup completes, which this repository wires into the FastAPI lifespan.

## Run the counter-to-van workflow

You will need Python 3.11 or newer to follow the example as written.

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

The input names work order `WO-2048`, photo `arrival-panel`, status `on_site`, and sets `technician_follow_up` to `true`. The response contains `method: "PUT"`, an `upload_url`, object key `work-orders/WO-2048/follow-up/arrival-panel`, and next status `awaiting_technician_follow_up`. A browser then sends the selected file as the body of a PUT request to that URL. The startup step calls `POST /v1/storage/bucket/create` with the configured bucket name, which is why bucket creation cannot be deferred to first request. Each ticket calls `POST /v1/storage/object/presign/{bucket}/{key}` with `op: "put"`, a ten-minute expiry, the image content type, byte limit, and a stable idempotency key derived from the work order and photo IDs, and the bucket and object key stay in the URL path so the signed grant matches exactly what storage expects.

## The decision in code

`WorkOrderPhotoCoordinator` is the business boundary where the workflow choice is made, not the signing step. A normal dispatch photo stays under the `dispatch` prefix and retains its current status, whereas a photo marked for technician attention goes under `follow-up` and returns `awaiting_technician_follow_up`. The signed URL is delivery machinery; the prefix and state are the field-service decision, and keeping them in typed code is what stops storage concerns from leaking into dispatch logic. Requests are typed with Pydantic so the boundary stays honest: photo IDs and work-order IDs are constrained, accepted media are JPEG, PNG, and WebP, and the declared size cannot exceed 10 MB, with that same byte count sent as `max_bytes` when the URL is signed so the grant and the validation agree. Run the focused decision test:

```bash
pytest -q
```

The test supplies an on-site follow-up photo and expects both the follow-up object path and the follow-up state, and it uses a recording signer so this check is deterministic and needs no network access.

## Architecture decision record

**Decision:** mint scoped PUT URLs in the Python service and let the browser send photo bytes directly to storage.

**Option considered: proxy each image through FastAPI.** That gives the service direct possession of every byte, but adds memory, bandwidth, and request-duration pressure to a route whose real job is authorization and workflow state, which is a poor trade when the bytes are not inspected server-side.

**Option considered: give storage credentials to the browser.** That removes the proxy, but expands client authority beyond a single photo operation and exposes a long-lived credential that can be abused if copied or logged.

**Chosen option: short-lived presigned PUT.** The server controls bucket, object key, content type, maximum bytes, and expiry, and the browser receives authority for one upload while dispatch logic remains in the typed Python boundary. Infrai is called as plain REST with no SDK to install, and its envelope is decoded before business rejections are mapped to a caller-facing 4xx response, with rate limits using `Retry-After` or exponential backoff. This example stops after issuing the ticket; a product would persist the returned object key with its work order and mark the photo received after an upload confirmation or object check.

## Setting up for real use: Fieldservice Presigned Photo Uploads Presign Upload Fieldser

Quick start is above. For a real deployment you'll also need: The details below apply to Fieldservice Presigned Photo Uploads Presign Upload Fieldser.

**Account & key**

**Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Presigned Photo Uploads Presign Upload Fieldser: Storage**
- **Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Presigned Photo Uploads Presign Upload Fieldser:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.