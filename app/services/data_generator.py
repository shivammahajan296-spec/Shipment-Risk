from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd


WAREHOUSES = ["ATL-01", "DAL-02", "LAX-01", "CHI-01", "NJ-01", "SEA-01"]
CARRIERS = ["FedEx", "UPS", "DHL", "XPO", "JB Hunt", "Maersk Inland"]
SERVICE_LEVELS = ["Standard", "Expedited", "Two-Day", "Priority Freight"]
PRIORITIES = ["Low", "Standard", "High", "Critical"]
REGIONS = {
    "Northeast": ["New York", "Boston", "Newark", "Philadelphia"],
    "South": ["Atlanta", "Miami", "Nashville", "Charlotte"],
    "Midwest": ["Chicago", "Detroit", "Columbus", "St. Louis"],
    "West": ["Los Angeles", "Phoenix", "Seattle", "Denver"],
    "Texas": ["Dallas", "Houston", "Austin", "San Antonio"],
}
STATES = {
    "New York": ("NY", "10001"),
    "Boston": ("MA", "02108"),
    "Newark": ("NJ", "07102"),
    "Philadelphia": ("PA", "19107"),
    "Atlanta": ("GA", "30303"),
    "Miami": ("FL", "33101"),
    "Nashville": ("TN", "37201"),
    "Charlotte": ("NC", "28202"),
    "Chicago": ("IL", "60601"),
    "Detroit": ("MI", "48201"),
    "Columbus": ("OH", "43004"),
    "St. Louis": ("MO", "63101"),
    "Los Angeles": ("CA", "90012"),
    "Phoenix": ("AZ", "85004"),
    "Seattle": ("WA", "98101"),
    "Denver": ("CO", "80202"),
    "Dallas": ("TX", "75201"),
    "Houston": ("TX", "77002"),
    "Austin": ("TX", "73301"),
    "San Antonio": ("TX", "78205"),
}


@dataclass
class SyntheticDatasetConfig:
    rows: int = 50000
    seed: int = 42
    months: int = 6


class SyntheticDataGenerator:
    def __init__(self, config: Optional[SyntheticDatasetConfig] = None) -> None:
        self.config = config or SyntheticDatasetConfig()
        self.rng = np.random.default_rng(self.config.seed)

    def generate(self) -> pd.DataFrame:
        now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        start_date = now - timedelta(days=30 * self.config.months)
        order_dates = pd.to_datetime(
            self.rng.integers(
                int(start_date.timestamp()),
                int(now.timestamp()),
                size=self.config.rows,
            ),
            unit="s",
        )

        warehouses = self.rng.choice(WAREHOUSES, size=self.config.rows, p=[0.16, 0.18, 0.22, 0.14, 0.18, 0.12])
        carriers = self.rng.choice(CARRIERS, size=self.config.rows, p=[0.24, 0.22, 0.13, 0.14, 0.15, 0.12])
        priorities = self.rng.choice(PRIORITIES, size=self.config.rows, p=[0.12, 0.48, 0.28, 0.12])
        service_levels = self.rng.choice(SERVICE_LEVELS, size=self.config.rows, p=[0.42, 0.24, 0.22, 0.12])
        regions = self.rng.choice(list(REGIONS.keys()), size=self.config.rows, p=[0.19, 0.18, 0.2, 0.25, 0.18])
        destination_cities = np.array([self.rng.choice(REGIONS[region]) for region in regions])

        pick_delay_hours = self.rng.normal(4.8, 2.4, self.config.rows).clip(0.8, 14)
        pack_delay_hours = self.rng.normal(1.8, 0.9, self.config.rows).clip(0.3, 6)
        dispatch_delay_hours = self.rng.normal(3.0, 1.4, self.config.rows).clip(0.5, 10)
        transit_days = self.rng.normal(3.4, 1.2, self.config.rows).clip(1, 8)

        warehouse_volume = self.rng.integers(280, 1450, size=self.config.rows)
        orders_per_picker = self.rng.normal(24, 6, self.config.rows).clip(8, 48)
        avg_pick_queue = self.rng.normal(24, 12, self.config.rows).clip(3, 95)
        pack_utilization = self.rng.normal(0.68, 0.1, self.config.rows).clip(0.35, 0.96)
        staffing_level = self.rng.normal(0.91, 0.06, self.config.rows).clip(0.62, 1.05)
        absenteeism_rate = self.rng.normal(0.05, 0.02, self.config.rows).clip(0.0, 0.18)
        shift_type = self.rng.choice(["Day", "Night", "Weekend"], size=self.config.rows, p=[0.62, 0.26, 0.12])
        dock_load = self.rng.normal(0.61, 0.14, self.config.rows).clip(0.18, 1.0)
        inventory_shortage = self.rng.binomial(1, 0.09, size=self.config.rows)
        backlog_index = self.rng.normal(38, 18, self.config.rows).clip(5, 140)

        carrier_on_time = self.rng.normal(0.935, 0.035, self.config.rows).clip(0.78, 0.995)
        carrier_avg_delay = self.rng.normal(0.9, 0.45, self.config.rows).clip(0.0, 4.0)
        carrier_exception_rate = self.rng.normal(0.05, 0.02, self.config.rows).clip(0.005, 0.18)
        carrier_capacity = self.rng.choice(["Normal", "Tight", "Constrained"], size=self.config.rows, p=[0.72, 0.2, 0.08])

        weather_severity = self.rng.normal(24, 16, self.config.rows).clip(0, 100)
        rain_flag = (weather_severity > 42).astype(int)
        snow_flag = ((destination_cities == "Chicago") | (destination_cities == "Detroit") | (destination_cities == "Boston")) & (weather_severity > 55)
        storm_alert = (weather_severity > 78).astype(int)
        traffic_congestion = self.rng.normal(36, 15, self.config.rows).clip(0, 100)
        road_closure = self.rng.binomial(1, 0.025, size=self.config.rows)
        strike_alert = self.rng.binomial(1, 0.015, size=self.config.rows)
        holiday_pressure = np.isin(order_dates.month, [11, 12]).astype(int)
        route_disruption = self.rng.normal(12, 10, self.config.rows).clip(0, 100)

        weight = self.rng.gamma(2.4, 18, self.config.rows).clip(1, 600)
        item_count = self.rng.integers(1, 40, size=self.config.rows)
        sku_count = np.minimum(item_count, self.rng.integers(1, 18, size=self.config.rows))
        fragile = self.rng.binomial(1, 0.16, size=self.config.rows)
        hazardous = self.rng.binomial(1, 0.04, size=self.config.rows)
        special_handling = np.maximum(fragile, hazardous)

        latent_risk = (
            0.42 * (avg_pick_queue / 100)
            + 0.56 * (1 - staffing_level)
            + 0.35 * absenteeism_rate
            + 0.32 * (backlog_index / 100)
            + 0.52 * inventory_shortage
            + 0.45 * (1 - carrier_on_time)
            + 0.32 * carrier_exception_rate
            + 0.5 * storm_alert
            + 0.28 * road_closure
            + 0.35 * strike_alert
            + 0.18 * holiday_pressure
            + 0.22 * (traffic_congestion / 100)
            + 0.18 * (route_disruption / 100)
            + np.where(priorities == "Critical", 0.08, np.where(priorities == "High", 0.03, 0.0))
            + np.where(carrier_capacity == "Constrained", 0.16, np.where(carrier_capacity == "Tight", 0.08, 0.0))
        )

        lane_stress = np.where(np.isin(regions, ["West", "Northeast"]), 0.05, 0.0)
        warehouse_stress = np.where(np.isin(warehouses, ["LAX-01", "DAL-02"]), 0.05, 0.0)
        delay_probability = 1 / (1 + np.exp(-(latent_risk * 3.4 - 2.8 + lane_stress + warehouse_stress)))
        delay_flag = self.rng.binomial(1, delay_probability)
        delay_days = np.where(delay_flag == 1, np.round(self.rng.gamma(1.7, 1.4, self.config.rows)).astype(int), 0)
        delay_days = np.clip(delay_days, 0, 7)

        pick_start = order_dates + pd.to_timedelta(self.rng.normal(1.2, 0.5, self.config.rows).clip(0.1, 4), unit="h")
        pick_complete = pick_start + pd.to_timedelta(pick_delay_hours, unit="h")
        pack_complete = pick_complete + pd.to_timedelta(pack_delay_hours, unit="h")
        dispatch_time = pack_complete + pd.to_timedelta(dispatch_delay_hours, unit="h")
        promised_delivery = dispatch_time + pd.to_timedelta(np.ceil(transit_days), unit="D")
        actual_delivery = promised_delivery + pd.to_timedelta(delay_days, unit="D")

        data = pd.DataFrame(
            {
                "shipment_id": [f"SHP-{100000+i}" for i in range(self.config.rows)],
                "order_id": [f"ORD-{500000+i}" for i in range(self.config.rows)],
                "order_creation_date": order_dates,
                "pick_start_time": pick_start,
                "pick_completion_time": pick_complete,
                "pack_completion_time": pack_complete,
                "dispatch_time": dispatch_time,
                "promised_delivery_date": promised_delivery,
                "actual_delivery_date": actual_delivery,
                "delay_flag": delay_flag,
                "delay_days": delay_days,
                "carrier": carriers,
                "service_level": service_levels,
                "origin_warehouse": warehouses,
                "destination_city": destination_cities,
                "destination_state": [STATES[city][0] for city in destination_cities],
                "destination_zip": [STATES[city][1] for city in destination_cities],
                "destination_region": regions,
                "shipment_weight": np.round(weight, 2),
                "item_count": item_count,
                "sku_count": sku_count,
                "priority": priorities,
                "fragile_flag": fragile,
                "hazardous_flag": hazardous,
                "special_handling_flag": special_handling,
                "warehouse_daily_order_volume": warehouse_volume,
                "orders_per_picker": np.round(orders_per_picker, 1),
                "average_pick_queue_time": np.round(avg_pick_queue, 1),
                "pack_station_utilization": np.round(pack_utilization, 3),
                "staffing_level": np.round(staffing_level, 3),
                "absenteeism_rate": np.round(absenteeism_rate, 3),
                "shift_type": shift_type,
                "dock_load": np.round(dock_load, 3),
                "inventory_shortage_flag": inventory_shortage,
                "backlog_index": np.round(backlog_index, 1),
                "carrier_on_time_pct": np.round(carrier_on_time, 3),
                "carrier_avg_delay_days": np.round(carrier_avg_delay, 2),
                "carrier_exception_rate": np.round(carrier_exception_rate, 3),
                "carrier_capacity_status": carrier_capacity,
                "weather_severity_score": np.round(weather_severity, 1),
                "rain_flag": rain_flag,
                "snow_flag": snow_flag.astype(int),
                "storm_alert_flag": storm_alert,
                "traffic_congestion_score": np.round(traffic_congestion, 1),
                "road_closure_flag": road_closure,
                "strike_alert_flag": strike_alert,
                "holiday_pressure_flag": holiday_pressure,
                "route_disruption_score": np.round(route_disruption, 1),
            }
        )

        return data.sort_values("order_creation_date").reset_index(drop=True)
