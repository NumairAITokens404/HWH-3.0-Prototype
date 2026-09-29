"""Exercise a fresh local API server over HTTP; the calls mutate its test database."""

import argparse
import json
import urllib.request
from pathlib import Path
from time import sleep
from urllib.parse import urlparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        parser.error("Use a fresh local HTTP server with temporary database paths")

    def call(method: str, path: str, body: bytes | None = None, content_type: str | None = None,
             extra_headers: dict[str, str] | None = None):
        headers = {"Content-Type": content_type} if content_type else {}
        headers.update(extra_headers or {})
        request = urllib.request.Request(base + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            result = json.loads(payload) if payload and response.headers.get_content_type() == "application/json" else payload
            print(f"{method} {path}: {response.status}")
            return result

    def post_json(path: str, value: dict):
        return call("POST", path, json.dumps(value).encode(), "application/json")

    health = call("GET", "/api/health")
    assert health["status"] == "ok" and health["memory_ready"]
    assert call("GET", "/health") == health
    call("OPTIONS", "/api/health", extra_headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
    })
    call("GET", "/api/capabilities")
    call("GET", "/api/demo/scenarios")
    assert call("GET", "/api/ui/incidents") == []
    call("GET", "/api/ui/overview")
    call("GET", "/api/ui/evaluation")
    call("GET", "/api/ui/uploads")

    source = Path(__file__).resolve().parents[1] / "data" / "remediation_history.json"
    boundary = "hwhsmokeboundary"
    file_body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{source.name}\"\r\nContent-Type: application/json\r\n\r\n").encode()
    file_body += source.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    upload = call("POST", "/api/memory/uploads", file_body, f"multipart/form-data; boundary={boundary}")
    assert upload["incident_count"] > 0
    incidents = call("GET", "/api/ui/incidents")
    assert incidents
    detail = call("GET", "/api/ui/incidents/TEST-001")
    assert detail["investigation"]["status"] == "RECOMMENDATION_READY"
    investigation = post_json("/api/incidents/investigate", detail["incident"])
    assert investigation["recommended_action"]
    low = call("POST", "/api/ui/incidents/TEST-001/workflow", b"", "application/json")
    assert low["status"] == "SUCCESS"
    pending = call("POST", "/api/ui/incidents/TEST-003/workflow", b"", "application/json")
    assert pending["status"] == "HUMAN_APPROVAL_REQUIRED"
    approved = post_json("/api/ui/incidents/TEST-003/approval", {
        "request_id": pending["decision"]["request_id"], "approved": True, "reviewer": "smoke-test",
    })
    assert approved["status"] == "SUCCESS"
    assert post_json("/api/demo/workflows", {"scenario": "low-risk-success"})["status"] == "SUCCESS"
    assert post_json("/api/demo/workflows", {"scenario": "partial-recovery"})["status"] == "PARTIAL"
    demo_pending = post_json("/api/demo/workflows", {"scenario": "high-risk-approval"})
    assert demo_pending["status"] == "HUMAN_APPROVAL_REQUIRED"
    demo_approved = post_json(f"/api/demo/workflows/{demo_pending['incident_id']}/approval", {
        "request_id": demo_pending["decision"]["request_id"],
        "approved": True, "reviewer": "smoke-test",
    })
    assert demo_approved["status"] == "SUCCESS"
    call("GET", "/api/ui/memory")
    call("GET", "/api/memory/failed-remediations?q=retry")
    call("GET", "/api/ui/overview")
    call("GET", "/api/ui/evaluation")
    call("POST", "/api/ui/evaluation/refresh", b"", "application/json")
    call("GET", "/api/ui/uploads")
    call("DELETE", f"/api/ui/uploads/{upload['upload_id']}")
    assert call("GET", "/api/ui/uploads") == []
    queued = call("POST", "/api/ui/uploads", file_body, f"multipart/form-data; boundary={boundary}")
    assert queued["stage"] in {"uploading", "embedding", "storing", "completed"}
    for _ in range(100):
        job = next(item for item in call("GET", "/api/ui/uploads") if item["id"] == queued["id"])
        if job["stage"] in {"completed", "failed"}:
            break
        sleep(0.1)
    assert job["stage"] == "completed", job
    call("DELETE", f"/api/ui/uploads/{queued['id']}")
    assert call("POST", "/api/ui/reset", b"", "application/json")["status"] == "RESET"
    assert call("GET", "/api/ui/incidents") == []
    call("GET", "/openapi.json")
    print("Live API smoke test passed")


if __name__ == "__main__":
    main()
