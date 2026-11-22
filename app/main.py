"""AI CAD v1: template CAD + sketch-photo interpretation (no generated code is ever executed)."""
import time
from collections import deque
import logging
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from build123d import export_step, export_stl
from starlette.concurrency import run_in_threadpool
from .templates import schema, generate_shape
from .vision import (extract_part, image_mime, is_configured, provider_name, MAX_IMAGE_BYTES, VisionNotConfigured,
                     VisionProviderError, ImageTooLarge, UnsupportedImageType)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.getenv("CAD_OUTPUT_DIR", str(ROOT.parent / "output"))).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CAD_LOCK = Lock()  # serialize OCCT operations, including multiple concurrent HTTP requests
app = FastAPI(title="Mohamed's AI CAD", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part_type: str
    dimensions: dict[str, Annotated[float, Field(strict=True)]]

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/templates")
def templates():
    return schema()

@app.get("/api/health")
def health():
    return {"status": "ok", "vision_configured": is_configured(), "vision_provider": provider_name(), "units": "mm"}

@app.post("/api/generate")
def generate(body: GenerateRequest):
    job_id = uuid4().hex
    folder = OUTPUT_DIR / job_id
    try:
        with CAD_LOCK:
            shape, report = generate_shape(body.part_type, body.dimensions)
            folder.mkdir()
            step = folder / "part.step"
            stl = folder / "part.stl"
            if not export_step(shape, str(step)):
                raise RuntimeError("STEP export failed")
            if not export_stl(shape, str(stl), tolerance=0.05, angular_tolerance=0.1):
                raise RuntimeError("STL export failed")
            if min(step.stat().st_size, stl.stat().st_size) <= 84:
                raise RuntimeError("Exported file is empty")
        return {"job_id": job_id, "part_type": body.part_type, "dimensions": body.dimensions,
                "validation": report, "step_url": f"/api/files/{job_id}/part.step",
                "stl_url": f"/api/files/{job_id}/part.stl"}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logging.exception("Generation failed for job %s", job_id)
        raise HTTPException(500, "CAD generation/export failed. Check server logs.") from exc
    finally:
        # Failed jobs do not expose a partial download.
        if folder.exists() and (not (folder/"part.step").exists() or not (folder/"part.stl").exists()):
            for path in folder.iterdir():
                path.unlink()
            folder.rmdir()

@app.get("/api/files/{job_id}/{filename}")
def download(job_id: str, filename: str):
    if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id) or filename not in {"part.step", "part.stl"}:
        raise HTTPException(404, "File not found")
    path = OUTPUT_DIR / job_id / filename
    if not path.is_file():
        raise HTTPException(404, "File not found")
    media = "model/step" if filename.endswith(".step") else "model/stl"
    return FileResponse(path, media_type=media, filename=filename)

# Public deployment: cap paid vision calls so nobody can burn the owner's API credit.
VISION_PER_IP_HOUR = int(os.getenv("VISION_MAX_PER_IP_HOUR", "10"))
VISION_GLOBAL_HOUR = int(os.getenv("VISION_MAX_PER_HOUR", "60"))
_vision_calls: dict[str, deque] = {}
_vision_global: deque = deque()
_vision_lock = Lock()


def _rate_ok(client: str) -> bool:
    now = time.monotonic()
    with _vision_lock:
        for q in (_vision_global, _vision_calls.setdefault(client, deque())):
            while q and now - q[0] > 3600:
                q.popleft()
        mine = _vision_calls[client]
        if len(mine) >= VISION_PER_IP_HOUR or len(_vision_global) >= VISION_GLOBAL_HOUR:
            return False
        mine.append(now); _vision_global.append(now)
        if len(_vision_calls) > 5000:
            _vision_calls.clear()
        return True


@app.post("/api/interpret")
async def interpret(request: Request, image: UploadFile = File(...)):
    try:
        if not is_configured():
            raise VisionNotConfigured("Sketch AI is disabled on this server. Manual CAD works without it.")
        data = await image.read(MAX_IMAGE_BYTES + 1)
        mime = image_mime(data)
        fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client = fwd or (request.client.host if request.client else "unknown")
        if not _rate_ok(client):
            raise HTTPException(429, "Too many sketch analyses right now. Try again later or use manual entry.")
        proposal = await run_in_threadpool(extract_part, data, mime)
        return {**proposal, "requires_confirmation": True,
                "warning": "Verify every dimension against the drawing before generating."}
    except ImageTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc
    except UnsupportedImageType as exc:
        raise HTTPException(415, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except VisionNotConfigured as exc:
        raise HTTPException(503, str(exc)) from exc
    except VisionProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    finally:
        await image.close()
