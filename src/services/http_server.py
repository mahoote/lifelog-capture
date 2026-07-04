from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.services import storage
from src.services.transfer_service import TransferService
from src.services.wifi_service import WifiService
from src.types.footage_item import FootageState

app = FastAPI()

transfer_service = TransferService()
wifi_service = WifiService()


class AckRequest(BaseModel):
    file_id: str


@app.get("/health")
def health():
    wifi = wifi_service.get_status()

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
        for item in storage.list_pending()
    ]


@app.post("/ack")
def ack_file(request: AckRequest):
    success = storage.update_state(request.file_id, FootageState.ACKED)

    if not success:
        raise HTTPException(status_code=404, detail="File not found")

    return {"ok": True}
