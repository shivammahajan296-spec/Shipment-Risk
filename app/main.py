from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import CopilotRequest, LLMSettingsRequest, LLMTestRequest, ScenarioRequest, UploadResponse
from app.services.platform_service import PlatformService


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

platform_service = PlatformService()
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    platform_service.initialize()


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/overview")
async def get_overview() -> dict:
    return platform_service.overview()


@app.get("/api/agents")
async def get_agents() -> dict:
    return await platform_service.agent_trace()


@app.post("/api/copilot")
async def copilot(payload: CopilotRequest) -> dict:
    return await platform_service.copilot_answer(payload.question)


@app.get("/api/llm/settings")
async def get_llm_settings() -> dict:
    return settings.llm_settings_view()


@app.post("/api/llm/settings")
async def save_llm_settings(payload: LLMSettingsRequest) -> dict:
    settings.save_runtime_overrides(
        straive_api_key=payload.straive_api_key,
        straive_model=payload.straive_model,
        use_mock_llm=False,
    )
    return {"status": "ok", **settings.llm_settings_view()}


@app.post("/api/llm/settings/clear")
async def clear_llm_settings() -> dict:
    settings.clear_runtime_overrides()
    return {"status": "ok", **settings.llm_settings_view()}


@app.post("/api/llm/settings/test")
async def test_llm_settings(payload: LLMTestRequest) -> dict:
    result = await platform_service.llm_service.test_connection(payload.prompt)
    return result


@app.get("/api/shipments")
async def get_shipments(limit: int = 150) -> dict:
    return {"rows": platform_service.shipment_table(limit=limit)}


@app.get("/api/shipments/{shipment_id}")
async def get_shipment_detail(shipment_id: str) -> dict:
    detail = platform_service.shipment_detail(shipment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return detail


@app.post("/api/simulate")
async def simulate_scenario(payload: ScenarioRequest) -> dict:
    return platform_service.simulate(payload.scenario_type, payload.region_or_entity, payload.severity)


@app.post("/api/demo/reset")
async def reset_demo() -> dict:
    platform_service.shipments = platform_service.generator.generate()
    platform_service.shipments.to_csv(settings.shipments_path, index=False)
    platform_service.refresh_analytics()
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")

    temp_path = settings.data_dir / f"upload{suffix}"
    with temp_path.open("wb") as output:
        output.write(await file.read())
    result = platform_service.upload(temp_path)
    return UploadResponse(**result)


@app.get("/api/export/shipments")
async def export_shipments() -> FileResponse:
    export_path = platform_service.export_shipments_csv()
    return FileResponse(export_path, filename="shipment_risk_export.csv", media_type="text/csv")
