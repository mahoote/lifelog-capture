from pathlib import Path

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.services import storage_service as storage
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
    return jsonable_encoder(storage.list_pending_capture_events())


@app.get("/footage/{file_id}")
def download_footage(file_id: str):
    item = storage.get_footage_item(file_id)

    if item is None:
        raise HTTPException(status_code=404, detail="File not found in database")

    file_path = Path(item.file_path)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream"
    )


@app.post("/ack")
def handle_ack(request: AckRequest):
    success = storage.update_footage_state(request.file_id, FootageState.ACKED)

    if not success:
        raise HTTPException(status_code=404, detail="File not found")

    return {"ok": True}


def _get_wifi_service(request: Request) -> WifiService:
    wifi_service = getattr(request.app.state, "wifi_service", None)

    if wifi_service is None:
        raise RuntimeError("WiFi service has not been configured")

    return wifi_service
