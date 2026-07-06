from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from src.services import storage_service
from src.services.wifi_service import WifiService
from src.types.footage_item import FootageState

app = FastAPI()


class AckRequest(BaseModel):
    file_id: str


@app.get("/health")
def health(request: Request):
    wifi = _get_wifi_service(request).get_status()

    return {
        "ok": True,
        "ssid": wifi.ssid,
        "ip": wifi.ip,
    }


@app.get("/footage")
def list_footage():
    return [
        {
            "id": str(item.id),
            "type": item.type,
            "created_at": item.created_at.isoformat(),
            "size_bytes": item.size_bytes,
            "motion_state": item.motion_state,
            "state": item.state,
            "attempt": item.attempt,
            "sha256": item.sha256,
            "duration_s": item.duration_s,
            "capture_end_at": item.capture_end_at.isoformat() if item.capture_end_at else None,
            "last_error": item.last_error,
        }
        for item in storage_service.list_pending()
    ]


@app.post("/ack")
def ack_file(request: AckRequest):
    success = storage_service.update_state(request.file_id, FootageState.ACKED)

    if not success:
        raise HTTPException(status_code=404, detail="File not found")

    return {"ok": True}


def _get_wifi_service(request: Request) -> WifiService:
    wifi_service = getattr(request.app.state, "wifi_service", None)

    if wifi_service is None:
        raise RuntimeError("WiFi service has not been configured")

    return wifi_service
