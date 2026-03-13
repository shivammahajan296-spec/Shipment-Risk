from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.config import settings
from app.models import KPIResponse
from app.services.agent_service import AgentContext, AgentOrchestrator
from app.services.data_generator import SyntheticDataGenerator
from app.services.decision_engine import DecisionEngine
from app.services.digital_twin import DigitalTwinService
from app.services.external_signals import MockSignalProvider
from app.services.llm_service import LLMService
from app.services.ml_service import MLRiskService


REQUIRED_FIELDS = {
    "shipment_id",
    "order_id",
    "order_creation_date",
    "dispatch_time",
    "promised_delivery_date",
    "actual_delivery_date",
    "carrier",
    "origin_warehouse",
    "destination_city",
    "destination_region",
    "delay_flag",
}


class PlatformService:
    def __init__(self) -> None:
        self.generator = SyntheticDataGenerator()
        self.ml_service = MLRiskService()
        self.signal_provider = MockSignalProvider()
        self.decision_engine = DecisionEngine()
        self.digital_twin = DigitalTwinService()
        self.llm_service = LLMService()
        self.agent_orchestrator = AgentOrchestrator(self.llm_service)
        self.shipments: Optional[pd.DataFrame] = None
        self.scored_shipments: Optional[pd.DataFrame] = None
        self.region_signals: Optional[pd.DataFrame] = None

    def initialize(self) -> None:
        if settings.shipments_path.exists():
            self.shipments = pd.read_csv(settings.shipments_path, parse_dates=[
                "order_creation_date",
                "pick_start_time",
                "pick_completion_time",
                "pack_completion_time",
                "dispatch_time",
                "promised_delivery_date",
                "actual_delivery_date",
            ])
        else:
            self.shipments = self.generator.generate()
            self.shipments.to_csv(settings.shipments_path, index=False)
        self.refresh_analytics()

    def refresh_analytics(self) -> None:
        if self.shipments is None:
            self.initialize()
        assert self.shipments is not None
        self.ml_service.train(self.shipments)
        self.scored_shipments = self.ml_service.score(self.shipments)
        self.region_signals = self.signal_provider.generate_region_signals(self.scored_shipments)
        self.scored_shipments.to_csv(settings.scored_shipments_path, index=False)

    def upload(self, file_path: Path) -> dict[str, Any]:
        if file_path.suffix.lower() == ".csv":
            data = pd.read_csv(file_path)
        else:
            data = pd.read_excel(file_path)
        missing_fields = sorted(REQUIRED_FIELDS - set(data.columns))
        readiness_score = max(0, round(100 - len(missing_fields) * 7 - data.isna().mean().mean() * 100, 1))
        self.shipments = data
        self.shipments.to_csv(settings.shipments_path, index=False)
        self.refresh_analytics()
        return {
            "rows_loaded": len(data),
            "readiness_score": readiness_score,
            "missing_fields": missing_fields,
        }

    def get_kpis(self) -> KPIResponse:
        assert self.scored_shipments is not None
        scored = self.scored_shipments
        delayed_mean = scored.loc[scored["delay_flag"] == 1, "delay_days"].mean()
        return KPIResponse(
            total_shipments=int(len(scored)),
            delayed_shipments=int(scored["delay_flag"].sum()),
            on_time_pct=round(float(100 * (1 - scored["delay_flag"].mean())), 1),
            average_delay_days=round(float(delayed_mean if pd.notna(delayed_mean) else 0.0), 2),
            high_risk_shipments=int((scored["risk_band"] == "High").sum()),
            top_affected_warehouse=str(scored.groupby("origin_warehouse")["risk_probability"].mean().idxmax()),
            top_affected_carrier=str(scored.groupby("carrier")["risk_probability"].mean().idxmax()),
            external_disruption_index=round(float(scored[["weather_severity_score", "traffic_congestion_score", "route_disruption_score"]].mean().mean()), 1),
        )

    def filters(self) -> dict[str, list[str]]:
        assert self.scored_shipments is not None
        scored = self.scored_shipments
        return {
            "warehouses": sorted(scored["origin_warehouse"].unique().tolist()),
            "carriers": sorted(scored["carrier"].unique().tolist()),
            "regions": sorted(scored["destination_region"].unique().tolist()),
            "priorities": sorted(scored["priority"].unique().tolist()),
            "risk_bands": ["Low", "Medium", "High"],
            "disruption_types": ["Weather", "Traffic", "Road Closure", "Strike", "Holiday Peak"],
        }

    def data_quality_summary(self) -> dict[str, Any]:
        assert self.shipments is not None
        shipments = self.shipments.copy()
        required_groups = {
            "Shipment history": [
                "shipment_id",
                "order_id",
                "order_creation_date",
                "pick_start_time",
                "pick_completion_time",
                "pack_completion_time",
                "dispatch_time",
                "promised_delivery_date",
                "actual_delivery_date",
            ],
            "Warehouse operations": [
                "warehouse_daily_order_volume",
                "orders_per_picker",
                "average_pick_queue_time",
                "pack_station_utilization",
                "staffing_level",
                "backlog_index",
            ],
            "Carrier performance": [
                "carrier",
                "carrier_on_time_pct",
                "carrier_avg_delay_days",
                "carrier_exception_rate",
            ],
            "External risk": [
                "weather_severity_score",
                "traffic_congestion_score",
                "road_closure_flag",
                "strike_alert_flag",
                "route_disruption_score",
            ],
        }
        missing_ratio = float(shipments.isna().mean().mean())
        sequence_valid = (
            (shipments["order_creation_date"] <= shipments["pick_start_time"])
            & (shipments["pick_start_time"] <= shipments["pick_completion_time"])
            & (shipments["pick_completion_time"] <= shipments["pack_completion_time"])
            & (shipments["pack_completion_time"] <= shipments["dispatch_time"])
            & (shipments["dispatch_time"] <= shipments["actual_delivery_date"])
        )
        sequence_integrity = float(sequence_valid.mean())
        recent = shipments.nlargest(min(5000, len(shipments)), "order_creation_date")
        earlier = shipments.nsmallest(min(5000, len(shipments)), "order_creation_date")
        drift_fields = ["average_pick_queue_time", "backlog_index", "carrier_on_time_pct", "weather_severity_score"]
        drift_rows = []
        for field in drift_fields:
            recent_mean = float(recent[field].mean())
            earlier_mean = float(earlier[field].mean())
            baseline = max(abs(earlier_mean), 1e-6)
            drift_pct = round(((recent_mean - earlier_mean) / baseline) * 100, 1)
            drift_rows.append({"field": field, "drift_pct": drift_pct})
        quality_score = round(max(0.0, 100 - missing_ratio * 100 - (1 - sequence_integrity) * 100 * 0.8 - sum(abs(row["drift_pct"]) for row in drift_rows) * 0.04), 1)
        validation_matrix = []
        for label, columns in required_groups.items():
            available = [column for column in columns if column in shipments.columns]
            completeness = 0.0 if not available else float(1 - shipments[available].isna().mean().mean())
            status = "Pass" if completeness >= 0.97 else "Watch" if completeness >= 0.9 else "Critical"
            validation_matrix.append(
                {
                    "title": label,
                    "value": f"{round(completeness * 100, 1)}%",
                    "status": status,
                    "copy": f"{len(available)} of {len(columns)} expected fields are mapped with usable quality.",
                }
            )
        anomaly_flags = [
            {
                "severity": "Critical" if sequence_integrity < 0.96 else "Pass",
                "title": "Timestamp sequence integrity",
                "detail": f"{round(sequence_integrity * 100, 1)}% of lifecycle records follow a valid operational sequence.",
            },
            {
                "severity": "Watch" if any(abs(row["drift_pct"]) > 12 for row in drift_rows) else "Pass",
                "title": "Recent data drift monitor",
                "detail": "Recent operating behavior is compared against earlier history to catch score distortion before modeling.",
            },
            {
                "severity": "Watch" if missing_ratio > 0.015 else "Pass",
                "title": "Null and exception coverage",
                "detail": f"Average field-level missingness is {round(missing_ratio * 100, 2)}% across the active dataset.",
            },
        ]
        coverage = [
            {"title": label, "value": f"{sum(column in shipments.columns for column in columns)} / {len(columns)} fields validated"}
            for label, columns in required_groups.items()
        ]
        return {
            "quality_score": quality_score,
            "sequence_integrity_pct": round(sequence_integrity * 100, 1),
            "missing_ratio_pct": round(missing_ratio * 100, 2),
            "validation_matrix": validation_matrix,
            "anomaly_flags": anomaly_flags,
            "coverage": coverage,
            "drift_rows": drift_rows,
        }

    def overview(self) -> dict[str, Any]:
        assert self.scored_shipments is not None and self.region_signals is not None and self.ml_service.artifacts is not None
        scored = self.scored_shipments
        quality = self.data_quality_summary()
        trend = (
            scored.assign(order_day=scored["order_creation_date"].dt.date)
            .groupby("order_day")
            .agg(delay_rate=("delay_flag", "mean"), avg_risk=("risk_probability", "mean"), shipments=("shipment_id", "count"))
            .tail(30)
            .reset_index()
        )
        carrier_breakdown = (
            scored.groupby("carrier")
            .agg(delay_rate=("delay_flag", "mean"), avg_risk=("risk_probability", "mean"), volume=("shipment_id", "count"))
            .reset_index()
        )
        warehouse_breakdown = (
            scored.groupby("origin_warehouse")
            .agg(delay_rate=("delay_flag", "mean"), avg_risk=("risk_probability", "mean"), backlog=("backlog_index", "mean"))
            .reset_index()
        )
        lane_breakdown = (
            scored.groupby(["origin_warehouse", "destination_region"])
            .agg(delay_rate=("delay_flag", "mean"), avg_risk=("risk_probability", "mean"), volume=("shipment_id", "count"))
            .reset_index()
            .sort_values("avg_risk", ascending=False)
            .head(12)
        )
        root_cause_breakdown = (
            scored["key_risk_driver"]
            .value_counts(normalize=True)
            .mul(100)
            .round(1)
            .rename_axis("cause")
            .reset_index(name="share")
        )
        high_risk = scored.loc[scored["risk_band"] == "High"].copy()
        if high_risk.empty:
            high_risk = scored.sort_values("risk_probability", ascending=False).head(2500).copy()
        high_risk["shipment_value"] = 180 + high_risk["item_count"] * 42 + high_risk["shipment_weight"] * 3.8
        high_risk["penalty_risk"] = high_risk["shipment_value"] * high_risk["risk_probability"] * 0.085
        high_risk["expedite_cost"] = 22 + high_risk["shipment_weight"] * 0.55 + high_risk["delay_days"] * 14
        alerts = [
            {
                "severity": "Critical",
                "title": f"{int((scored['risk_probability'] >= 0.42).sum())} shipments likely to miss SLA",
                "detail": "Predicted breach count based on current risk threshold and promised delivery exposure.",
            },
            {
                "severity": "High",
                "title": f"{scored.groupby('origin_warehouse')['backlog_index'].mean().idxmax()} backlog exceeded watch threshold",
                "detail": "Backlog and pick-queue pressure are above the network median and need intervention.",
            },
            {
                "severity": "Medium",
                "title": f"{scored.groupby('carrier')['carrier_on_time_pct'].mean().idxmin()} reliability is lowest in the network",
                "detail": "Carrier service stability has deteriorated relative to peers and should be escalated.",
            },
        ]
        timeline = [
            {"time": "10:30 AM", "event": f"{self.region_signals.sort_values('disruption_severity', ascending=False).iloc[0]['destination_region']} disruption cluster detected"},
            {"time": "10:35 AM", "event": f"{int((scored['risk_probability'] >= 0.42).sum())} shipments flagged for SLA watchlist"},
            {"time": "10:38 AM", "event": f"Carrier escalation recommended for {scored.groupby('carrier')['risk_probability'].mean().idxmax()}"},
            {"time": "10:40 AM", "event": "Rerouting and staffing mitigation options generated"},
        ]
        action_simulations = [
            {
                "action": "Escalate lowest-performing carrier",
                "target": scored.groupby("carrier")["risk_probability"].mean().idxmax(),
                "before": round(float(scored["risk_probability"].quantile(0.9)), 2),
                "after": round(float(max(0.12, scored["risk_probability"].quantile(0.9) - 0.14)), 2),
                "effect": "Reallocates high-risk freight to a more reliable carrier mix.",
            },
            {
                "action": "Add temporary warehouse staffing",
                "target": scored.groupby("origin_warehouse")["backlog_index"].mean().idxmax(),
                "before": round(float(scored["risk_probability"].mean()), 2),
                "after": round(float(max(0.08, scored["risk_probability"].mean() - 0.06)), 2),
                "effect": "Relieves pick queue and backlog pressure on the most constrained node.",
            },
            {
                "action": "Expedite disruption-exposed shipments",
                "target": self.region_signals.sort_values("disruption_severity", ascending=False).iloc[0]["destination_region"],
                "before": round(float(high_risk["risk_probability"].mean()), 2),
                "after": round(float(max(0.1, high_risk["risk_probability"].mean() - 0.11)), 2),
                "effect": "Targets the subset of shipments most exposed to route and disruption friction.",
            },
        ]
        warehouse_heatmap = (
            scored.groupby("origin_warehouse")
            .agg(avg_risk=("risk_probability", "mean"), utilization=("pack_station_utilization", "mean"))
            .reset_index()
        )
        warehouse_heatmap["status"] = pd.cut(
            warehouse_heatmap["avg_risk"],
            bins=[-0.01, 0.24, 0.38, 1.01],
            labels=["Low", "Watch", "Critical"],
        ).astype(str)
        carrier_reliability = (
            scored.groupby("carrier")
            .agg(
                reliability=("carrier_on_time_pct", "mean"),
                exception_rate=("carrier_exception_rate", "mean"),
                avg_risk=("risk_probability", "mean"),
            )
            .reset_index()
            .sort_values("reliability", ascending=False)
        )
        network_graph = self.digital_twin.build_network(scored)
        decision_actions = self.decision_engine.generate_actions(scored, self.region_signals)
        operational_insights = [
            f"{top['cause']} is driving {top['share']}% of current predicted delay exposure."
            for top in root_cause_breakdown.head(3).to_dict(orient="records")
        ]
        agent_status = [
            {"name": "Data Integrity Agent", "status": "active"},
            {"name": "Risk Scoring Agent", "status": "active"},
            {"name": "Disruption Monitoring Agent", "status": "active"},
            {"name": "Decision Intelligence Agent", "status": "active"},
            {"name": "Simulation Agent", "status": "active"},
        ]
        return {
            "kpis": self.get_kpis().model_dump(),
            "filters": self.filters(),
            "data_quality": quality,
            "risk_band_counts": scored["risk_band"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0).to_dict(),
            "trend": trend.to_dict(orient="records"),
            "carrier_breakdown": carrier_breakdown.to_dict(orient="records"),
            "warehouse_breakdown": warehouse_breakdown.to_dict(orient="records"),
            "lane_breakdown": lane_breakdown.to_dict(orient="records"),
            "feature_importance": self.ml_service.artifacts.feature_importance,
            "model_metrics": self.ml_service.artifacts.metrics,
            "calibration": self.ml_service.artifacts.calibration,
            "region_signals": self.region_signals.to_dict(orient="records"),
            "top_recommendations": scored["recommended_action"].value_counts().rename_axis("action").reset_index(name="count").head(4).to_dict(orient="records"),
            "root_cause_breakdown": root_cause_breakdown.to_dict(orient="records"),
            "financial_exposure": {
                "high_risk_shipments_value": round(float(high_risk["shipment_value"].sum()), 0),
                "estimated_penalty_risk": round(float(high_risk["penalty_risk"].sum()), 0),
                "potential_expedite_cost": round(float(high_risk["expedite_cost"].sum()), 0),
            },
            "sla_breach_prediction": {
                "predicted_breach_shipments": int((scored["risk_probability"] >= 0.42).sum()),
                "breach_rate": round(float((scored["risk_probability"] >= 0.42).mean() * 100), 1),
            },
            "lane_intelligence": lane_breakdown.head(6).assign(
                lane=lambda df: df["origin_warehouse"] + " → " + df["destination_region"]
            )[["lane", "avg_risk", "delay_rate", "volume"]].to_dict(orient="records"),
            "capacity_stress": warehouse_breakdown.assign(
                utilization=scored.groupby("origin_warehouse")["pack_station_utilization"].mean().values
            ).sort_values("utilization", ascending=False).to_dict(orient="records"),
            "carrier_reliability": carrier_reliability.to_dict(orient="records"),
            "warehouse_heatmap": warehouse_heatmap.to_dict(orient="records"),
            "alerts": alerts,
            "operational_timeline": timeline,
            "action_simulations": action_simulations,
            "decision_actions": decision_actions,
            "operational_insights": operational_insights,
            "agent_status": agent_status,
            "network_graph": network_graph,
            "playbooks": self.decision_engine.generate_playbooks(),
            "executive_narrative": (
                f"Today's network risk is elevated around {self.get_kpis().top_affected_warehouse} and "
                f"{self.region_signals.sort_values('disruption_severity', ascending=False).iloc[0]['destination_region']}. "
                f"If no action is taken, {int((scored['risk_probability'] >= 0.42).sum())} shipments are likely to miss SLA. "
                f"Best near-term move: {decision_actions[0]['option']} with ROI {decision_actions[0]['roi']}."
            ),
            "learning_loop": {
                "predicted_delay_avg": round(float(scored["risk_probability"].mean() * 100), 1),
                "actual_delay_rate": round(float(scored["delay_flag"].mean() * 100), 1),
                "status": "Model feedback loop ready for retraining on completed shipments",
            },
            "top_shipments": self.shipment_table(limit=150),
        }

    def shipment_table(self, limit: int = 200) -> list[dict[str, Any]]:
        assert self.scored_shipments is not None
        top = self.scored_shipments.sort_values("risk_probability", ascending=False).head(limit).copy()
        top["destination"] = top["destination_city"] + ", " + top["destination_state"]
        for column in ["promised_delivery_date", "actual_delivery_date"]:
            top[column] = pd.to_datetime(top[column]).dt.strftime("%Y-%m-%d")
        return top[
            [
                "shipment_id",
                "order_id",
                "destination",
                "carrier",
                "origin_warehouse",
                "priority",
                "promised_delivery_date",
                "actual_delivery_date",
                "delay_flag",
                "delay_days",
                "risk_probability",
                "risk_band",
                "key_risk_driver",
                "risk_summary",
                "recommended_action",
                "external_overlays",
            ]
        ].to_dict(orient="records")

    def shipment_detail(self, shipment_id: str) -> dict[str, Any]:
        assert self.scored_shipments is not None
        match = self.scored_shipments.loc[self.scored_shipments["shipment_id"] == shipment_id]
        if match.empty:
            return {}
        row = match.iloc[0]
        reason_scores = {
            "warehouse_backlog": round(float(row["backlog_index"] * 0.25 + row["average_pick_queue_time"] * 0.18), 1),
            "staffing_strain": round(float((1 - row["staffing_level"]) * 100 + row["absenteeism_rate"] * 70), 1),
            "carrier_reliability": round(float((1 - row["carrier_on_time_pct"]) * 100 + row["carrier_exception_rate"] * 75), 1),
            "external_disruption": round(float(row["weather_severity_score"] * 0.45 + row["traffic_congestion_score"] * 0.25 + row["route_disruption_score"] * 0.3), 1),
        }
        return {
            "shipment_id": row["shipment_id"],
            "order_id": row["order_id"],
            "destination": f'{row["destination_city"]}, {row["destination_state"]}',
            "carrier": row["carrier"],
            "origin_warehouse": row["origin_warehouse"],
            "priority": row["priority"],
            "service_level": row["service_level"],
            "risk_probability": round(float(row["risk_probability"]), 4),
            "risk_band": row["risk_band"],
            "recommended_action": row["recommended_action"],
            "risk_summary": row["risk_summary"],
            "external_overlays": row["external_overlays"],
            "reason_scores": reason_scores,
            "shipment_lifecycle": [
                {"stage": "Order Created", "time": pd.to_datetime(row["order_creation_date"]).strftime("%Y-%m-%d %H:%M")},
                {"stage": "Picking Started", "time": pd.to_datetime(row["pick_start_time"]).strftime("%Y-%m-%d %H:%M")},
                {"stage": "Picking Completed", "time": pd.to_datetime(row["pick_completion_time"]).strftime("%Y-%m-%d %H:%M")},
                {"stage": "Packing Completed", "time": pd.to_datetime(row["pack_completion_time"]).strftime("%Y-%m-%d %H:%M")},
                {"stage": "Carrier Pickup", "time": pd.to_datetime(row["dispatch_time"]).strftime("%Y-%m-%d %H:%M")},
                {"stage": "Delivered", "time": pd.to_datetime(row["actual_delivery_date"]).strftime("%Y-%m-%d %H:%M")},
            ],
            "operational_snapshot": {
                "average_pick_queue_time": float(row["average_pick_queue_time"]),
                "staffing_level": float(row["staffing_level"]),
                "backlog_index": float(row["backlog_index"]),
                "carrier_on_time_pct": float(row["carrier_on_time_pct"]),
                "weather_severity_score": float(row["weather_severity_score"]),
                "traffic_congestion_score": float(row["traffic_congestion_score"]),
            },
        }

    def export_shipments_csv(self) -> Path:
        assert self.scored_shipments is not None
        export_path = settings.data_dir / "shipment_risk_export.csv"
        self.scored_shipments.to_csv(export_path, index=False)
        return export_path

    async def agent_trace(self) -> dict[str, Any]:
        assert self.shipments is not None and self.scored_shipments is not None and self.region_signals is not None and self.ml_service.artifacts is not None
        trace, executive_summary = await self.agent_orchestrator.run(
            AgentContext(
                shipments=self.shipments,
                scored_shipments=self.scored_shipments,
                metrics=self.ml_service.artifacts.metrics,
                feature_importance=self.ml_service.artifacts.feature_importance,
                region_signals=self.region_signals,
            )
        )
        return {
            "trace": [message.model_dump() for message in trace],
            "executive_summary": executive_summary,
        }

    async def copilot_answer(self, question: str) -> dict[str, Any]:
        assert self.scored_shipments is not None
        top_driver = str(self.scored_shipments["key_risk_driver"].value_counts().idxmax())
        top_warehouse = str(self.scored_shipments.groupby("origin_warehouse")["risk_probability"].mean().idxmax())
        top_actions = self.scored_shipments["recommended_action"].value_counts().head(3).index.tolist()
        response = await self.llm_service.answer_copilot(
            question,
            {
                "top_driver": top_driver,
                "top_warehouse": top_warehouse,
                "top_actions": top_actions,
                "predicted_breach_shipments": int((self.scored_shipments["risk_probability"] >= 0.42).sum()),
            },
        )
        return {
            "question": question,
            "answer": response,
        }

    def simulate(self, scenario_type: str, region_or_entity: str, severity: int) -> dict[str, Any]:
        assert self.shipments is not None
        simulated_shipments = self.signal_provider.apply_scenario(self.shipments, scenario_type, region_or_entity, severity)
        simulated_scored = self.ml_service.score(simulated_shipments)
        impacted = simulated_scored.sort_values("risk_probability", ascending=False).head(50).copy()
        impacted["destination"] = impacted["destination_city"] + ", " + impacted["destination_state"]
        return {
            "summary": {
                "avg_risk_before": round(float(self.scored_shipments["risk_probability"].mean()), 3) if self.scored_shipments is not None else 0.0,
                "avg_risk_after": round(float(simulated_scored["risk_probability"].mean()), 3),
                "high_risk_after": int((simulated_scored["risk_band"] == "High").sum()),
                "impacted_lanes": int(simulated_scored.groupby(["origin_warehouse", "destination_region"]).size().shape[0]),
            },
            "impacted_shipments": impacted[
                ["shipment_id", "destination", "carrier", "origin_warehouse", "risk_probability", "risk_band", "key_risk_driver", "recommended_action"]
            ].to_dict(orient="records"),
        }
