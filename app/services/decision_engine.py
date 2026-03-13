from __future__ import annotations

from typing import Any

import pandas as pd


class DecisionEngine:
    def generate_actions(self, scored: pd.DataFrame, region_signals: pd.DataFrame) -> list[dict[str, Any]]:
        top_warehouse = str(scored.groupby("origin_warehouse")["risk_probability"].mean().idxmax())
        top_carrier = str(scored.groupby("carrier")["risk_probability"].mean().idxmax())
        top_region = str(region_signals.sort_values("disruption_severity", ascending=False).iloc[0]["destination_region"])
        top_lane = (
            scored.groupby(["origin_warehouse", "destination_region"])["risk_probability"]
            .mean()
            .sort_values(ascending=False)
            .index[0]
        )
        actions = [
            {
                "title": "Reroute high-risk lane volume",
                "problem": f"{top_lane[0]} to {top_lane[1]} is carrying the highest concentration of predicted delay risk.",
                "option": f"Shift 40% of impacted volume away from {top_lane[0]} and prioritize alternate routing.",
                "delay_reduction_pct": 18,
                "cost_impact": 3200,
                "sla_saved": 410,
            },
            {
                "title": "Add temporary warehouse labor",
                "problem": f"{top_warehouse} backlog and pick-queue pressure are amplifying delay exposure across active shipments.",
                "option": f"Add 4 flex workers for the next shift at {top_warehouse}.",
                "delay_reduction_pct": 12,
                "cost_impact": 1400,
                "sla_saved": 290,
            },
            {
                "title": "Switch lowest-performing carrier mix",
                "problem": f"{top_carrier} is the weakest reliability node in the current portfolio.",
                "option": f"Shift time-sensitive shipments away from {top_carrier} on disruption-exposed lanes.",
                "delay_reduction_pct": 22,
                "cost_impact": 4100,
                "sla_saved": 510,
            },
            {
                "title": "Pre-emptively expedite disruption-exposed shipments",
                "problem": f"{top_region} external disruption intensity is likely to push medium-risk shipments into SLA breach.",
                "option": f"Expedite the highest-risk subset headed into {top_region}.",
                "delay_reduction_pct": 15,
                "cost_impact": 2600,
                "sla_saved": 335,
            },
        ]
        for action in actions:
            action["roi"] = round(action["sla_saved"] / max(action["cost_impact"], 1), 3)
            action["rank_score"] = round(action["delay_reduction_pct"] * 0.55 + action["sla_saved"] * 0.03 - action["cost_impact"] * 0.0015, 2)
        return sorted(actions, key=lambda item: item["rank_score"], reverse=True)

    def generate_playbooks(self) -> list[dict[str, str]]:
        return [
            {
                "name": "Backlog escalation",
                "rule": "If delay risk > 60% and warehouse backlog > threshold, trigger staffing escalation.",
            },
            {
                "name": "Weather reroute",
                "rule": "If weather severity > 8 and lane risk is elevated, pre-reroute shipments before dispatch.",
            },
            {
                "name": "Carrier reliability fallback",
                "rule": "If carrier reliability drops below network threshold, switch critical orders to alternate carrier.",
            },
        ]
