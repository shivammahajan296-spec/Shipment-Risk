from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd


class SignalProvider(Protocol):
    def generate_region_signals(self, shipments: pd.DataFrame) -> pd.DataFrame:
        ...

    def apply_scenario(self, shipments: pd.DataFrame, scenario_type: str, region_or_entity: str, severity: int) -> pd.DataFrame:
        ...


@dataclass
class MockSignalProvider:
    seed: int = 17

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)

    def generate_region_signals(self, shipments: pd.DataFrame) -> pd.DataFrame:
        grouped = shipments.groupby("destination_region").agg(
            impacted_shipments=("shipment_id", "count"),
            avg_weather=("weather_severity_score", "mean"),
            avg_traffic=("traffic_congestion_score", "mean"),
            closures=("road_closure_flag", "sum"),
            strikes=("strike_alert_flag", "sum"),
            route_disruption=("route_disruption_score", "mean"),
        )
        grouped["regional_incident_alerts"] = self.rng.integers(0, 5, len(grouped))
        grouped["port_congestion_score"] = self.rng.normal(25, 14, len(grouped)).clip(0, 100)
        grouped["disruption_severity"] = (
            grouped["avg_weather"] * 0.24
            + grouped["avg_traffic"] * 0.22
            + grouped["closures"] * 3.8
            + grouped["strikes"] * 5.2
            + grouped["route_disruption"] * 0.24
            + grouped["regional_incident_alerts"] * 4
            + grouped["port_congestion_score"] * 0.16
        ).round(1)
        return grouped.reset_index()

    def apply_scenario(self, shipments: pd.DataFrame, scenario_type: str, region_or_entity: str, severity: int) -> pd.DataFrame:
        simulated = shipments.copy()
        factor = severity / 5
        if scenario_type == "storm_region":
            mask = simulated["destination_region"].eq(region_or_entity)
            simulated.loc[mask, "weather_severity_score"] = np.clip(simulated.loc[mask, "weather_severity_score"] + 35 * factor, 0, 100)
            simulated.loc[mask, "storm_alert_flag"] = 1
            simulated.loc[mask, "route_disruption_score"] = np.clip(simulated.loc[mask, "route_disruption_score"] + 18 * factor, 0, 100)
        elif scenario_type == "warehouse_strike":
            mask = simulated["origin_warehouse"].eq(region_or_entity)
            simulated.loc[mask, "strike_alert_flag"] = 1
            simulated.loc[mask, "backlog_index"] = simulated.loc[mask, "backlog_index"] + 26 * factor
            simulated.loc[mask, "staffing_level"] = np.clip(simulated.loc[mask, "staffing_level"] - 0.22 * factor, 0.45, 1.05)
        elif scenario_type == "carrier_underperformance":
            mask = simulated["carrier"].eq(region_or_entity)
            simulated.loc[mask, "carrier_on_time_pct"] = np.clip(simulated.loc[mask, "carrier_on_time_pct"] - 0.18 * factor, 0.55, 0.99)
            simulated.loc[mask, "carrier_exception_rate"] = np.clip(simulated.loc[mask, "carrier_exception_rate"] + 0.08 * factor, 0, 0.35)
        elif scenario_type == "staffing_shortage":
            mask = simulated["origin_warehouse"].eq(region_or_entity)
            simulated.loc[mask, "staffing_level"] = np.clip(simulated.loc[mask, "staffing_level"] - 0.25 * factor, 0.45, 1.05)
            simulated.loc[mask, "average_pick_queue_time"] = simulated.loc[mask, "average_pick_queue_time"] + 28 * factor
        elif scenario_type == "backlog_spike":
            mask = simulated["origin_warehouse"].eq(region_or_entity)
            simulated.loc[mask, "backlog_index"] = simulated.loc[mask, "backlog_index"] + 38 * factor
            simulated.loc[mask, "dock_load"] = np.clip(simulated.loc[mask, "dock_load"] + 0.18 * factor, 0, 1)
        return simulated
