from __future__ import annotations

import json
import urllib.request


payload = {
    "work_order_id": "WO-2048",
    "photo_id": "arrival-panel",
    "content_type": "image/jpeg",
    "byte_size": 2_400_000,
    "dispatch_status": "on_site",
    "technician_follow_up": True,
}
request = urllib.request.Request(
    "http://127.0.0.1:8000/work-orders/photo-upload",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))

