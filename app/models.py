from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class KPIResponse(BaseModel):
    total_shipments: int
    delayed_shipments: int
    on_time_pct: float
    average_delay_days: float
    high_risk_shipments: int
    top_affected_warehouse: str
    top_affected_carrier: str
    external_disruption_index: float


class ShipmentRiskRow(BaseModel):
    shipment_id: str
    order_id: str
    destination: str
    carrier: str
    origin_warehouse: str
    priority: str
    promised_delivery_date: str
    actual_delivery_date: Optional[str]
    delay_flag: int
    delay_days: int
    risk_probability: float
    risk_band: Literal["Low", "Medium", "High"]
    key_risk_driver: str
    recommended_action: str
    external_overlays: list[str]


class ScenarioRequest(BaseModel):
    scenario_type: Literal[
        "storm_region",
        "warehouse_strike",
        "carrier_underperformance",
        "staffing_shortage",
        "backlog_spike",
    ]
    region_or_entity: str = Field(..., description="Region, warehouse, or carrier depending on scenario")
    severity: int = Field(ge=1, le=5, default=3)


class AgentMessage(BaseModel):
    agent: str
    phase: str
    summary: str
    payload: dict[str, Any]


class AgentRunResponse(BaseModel):
    trace: list[AgentMessage]
    executive_summary: str


class UploadResponse(BaseModel):
    rows_loaded: int
    readiness_score: float
    missing_fields: list[str]


class CopilotRequest(BaseModel):
    question: str


class LLMSettingsRequest(BaseModel):
    straive_api_key: str
    straive_model: str = "gemini-2.5-pro"


class LLMTestRequest(BaseModel):
    prompt: str = "Summarize the current network risk posture in one sentence."
