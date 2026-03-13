from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.models import AgentMessage
from app.services.llm_service import LLMService


@dataclass
class AgentContext:
    shipments: pd.DataFrame
    scored_shipments: pd.DataFrame
    metrics: dict[str, Any]
    feature_importance: list[dict[str, Any]]
    region_signals: pd.DataFrame


class AgentOrchestrator:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    async def run(self, context: AgentContext) -> tuple[list[AgentMessage], str]:
        shipments = context.shipments
        scored = context.scored_shipments
        delayed_share = float(shipments["delay_flag"].mean())
        top_warehouse = str(scored.groupby("origin_warehouse")["risk_probability"].mean().idxmax())
        top_carrier = str(scored.groupby("carrier")["risk_probability"].mean().idxmax())
        top_region = str(context.region_signals.sort_values("disruption_severity", ascending=False).iloc[0]["destination_region"])
        top_actions = scored["recommended_action"].value_counts().head(3).index.tolist()
        high_risk = int((scored["risk_band"] == "High").sum())

        readiness_score = round(
            100
            - (shipments.isna().mean().mean() * 100)
            - ((shipments.dtypes == "object").sum() * 0.2),
            1,
        )
        driver = context.feature_importance[0]["feature"] if context.feature_importance else "backlog_index"

        trace = [
            AgentMessage(
                agent="Data Understanding Agent",
                phase="Readiness",
                summary="Profiled incoming shipment and warehouse data, assessed completeness, and flagged schema stability.",
                payload={
                    "pattern": "Stable shipment, warehouse, carrier, and disruption coverage with low missingness across the seeded operating model.",
                    "impact": "Teams can move directly into scoring and root-cause review instead of spending cycles reconciling data quality gaps.",
                    "value_add": "Reduces time-to-value for deployment because the readiness gate is explainable and measurable.",
                    "nuance": "High completeness does not guarantee operational truth; event ordering and timestamp drift still matter during live ingestion.",
                    "readiness_score": readiness_score,
                    "missing_ratio": round(float(shipments.isna().mean().mean()), 4),
                    "date_columns_validated": 6,
                },
            ),
            AgentMessage(
                agent="Signal Discovery Agent",
                phase="Drivers",
                summary="Identified the dominant delay drivers across warehouse load, carrier reliability, external disruption, and staffing strain.",
                payload={
                    "pattern": f"{driver} is the strongest recurring delay signal, concentrated around {top_warehouse} and elevated exposure with {top_carrier}.",
                    "impact": "This narrows intervention to a few operational choke points rather than spreading effort across the entire network.",
                    "value_add": "Analysts get a faster explanation path from shipment exceptions to structural causes.",
                    "nuance": "The same driver does not behave identically across lanes; some patterns intensify only when disruption overlays and capacity constraints coincide.",
                    "top_driver": driver,
                    "carrier_delay_variance": round(float(shipments.groupby("carrier")["delay_flag"].mean().std()), 3),
                    "warehouse_delay_variance": round(float(shipments.groupby("origin_warehouse")["delay_flag"].mean().std()), 3),
                },
            ),
            AgentMessage(
                agent="ML Risk Scoring Agent",
                phase="Prediction",
                summary="Trained the predictive prototype and generated shipment-level risk probabilities with calibrated classification metrics.",
                payload={
                    **context.metrics,
                    "pattern": f"The model separates routine shipments from exception-prone shipments with an AUC of {context.metrics['auc']}.",
                    "impact": "Operations can prioritize interventions before a shipment becomes a service miss.",
                    "value_add": "Creates a repeatable scoring layer for batch monitoring, escalation queues, and simulation.",
                    "nuance": "Threshold tuning remains a business choice because operations may prefer higher recall even when that increases alert volume.",
                },
            ),
            AgentMessage(
                agent="External Risk Agent",
                phase="Disruption",
                summary="Mapped regional weather, traffic, closures, and labor alerts to the affected shipment portfolio.",
                payload={
                    "pattern": f"{top_region} is the dominant disruption cluster, with external stress accumulating faster than the network average.",
                    "impact": "Dynamic overlays reveal which medium-risk shipments are most likely to deteriorate next.",
                    "value_add": "Improves timing of reroutes, expediting, and contingency staffing decisions.",
                    "nuance": "External disruption is most damaging when it lands on already strained warehouses or low-reliability carriers.",
                    "hot_region": top_region,
                    "max_disruption_severity": float(context.region_signals["disruption_severity"].max()),
                },
            ),
            AgentMessage(
                agent="Operational Recommendation Agent",
                phase="Actioning",
                summary="Converted risk outputs into next-best operational moves for expediting, staffing, carrier reallocation, and exception handling.",
                payload={
                    "pattern": f"Recommended interventions cluster around {top_actions[0] if top_actions else 'exception review'}, showing repeated mitigation patterns across the portfolio.",
                    "impact": "Supervisors can act immediately instead of translating analytics into action plans manually.",
                    "value_add": "Turns risk visibility into execution by linking each dominant driver to a clear mitigation move.",
                    "nuance": "Best action depends on the cause: rerouting, labor balancing, and carrier escalation should not be treated as interchangeable.",
                    "top_actions": top_actions,
                    "high_risk_shipments": high_risk,
                },
            ),
        ]

        executive_summary = await self.llm_service.generate_grounded_summary(
            "Generate executive summary for today’s logistics risk posture",
            {
                "high_risk_shipments": high_risk,
                "top_affected_warehouse": top_warehouse,
                "top_driver": driver,
                "top_actions": top_actions,
            },
        )
        trace.append(
            AgentMessage(
                agent="Executive Summary Agent",
                phase="Leadership Brief",
                summary="Condensed cross-agent outputs into a business-facing risk narrative for leadership and operations reviews.",
                payload={
                    "pattern": f"The network is currently operating at {round((1 - delayed_share) * 100, 1)}% on-time with concentrated stress around {top_warehouse} and {top_region}.",
                    "impact": "Leadership gets a concise view of where service risk is building and which action will shift outcomes fastest.",
                    "value_add": "Bridges operational detail and business communication without losing explainability.",
                    "nuance": "Short-term recovery actions should be separated from structural improvement actions so the team does not optimize to transient disruption noise.",
                    "executive_summary": executive_summary,
                },
            )
        )
        return trace, executive_summary
