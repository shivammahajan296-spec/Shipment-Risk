from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = [
    "carrier",
    "service_level",
    "origin_warehouse",
    "destination_region",
    "priority",
    "shift_type",
    "carrier_capacity_status",
    "shipment_weight",
    "item_count",
    "sku_count",
    "warehouse_daily_order_volume",
    "orders_per_picker",
    "average_pick_queue_time",
    "pack_station_utilization",
    "staffing_level",
    "absenteeism_rate",
    "dock_load",
    "inventory_shortage_flag",
    "backlog_index",
    "carrier_on_time_pct",
    "carrier_avg_delay_days",
    "carrier_exception_rate",
    "weather_severity_score",
    "rain_flag",
    "snow_flag",
    "storm_alert_flag",
    "traffic_congestion_score",
    "road_closure_flag",
    "strike_alert_flag",
    "holiday_pressure_flag",
    "route_disruption_score",
    "fragile_flag",
    "hazardous_flag",
    "special_handling_flag",
]


@dataclass
class ModelArtifacts:
    model: Pipeline
    metrics: dict[str, Any]
    feature_importance: list[dict[str, Any]]
    calibration: list[dict[str, float]]


class MLRiskService:
    def __init__(self) -> None:
        self.artifacts: Optional[ModelArtifacts] = None

    def train(self, shipments: pd.DataFrame) -> ModelArtifacts:
        df = shipments.copy()
        X = df[FEATURE_COLUMNS]
        y = df["delay_flag"]

        categorical = [column for column in FEATURE_COLUMNS if X[column].dtype == "object"]
        numeric = [column for column in FEATURE_COLUMNS if column not in categorical]

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "categorical",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("encoder", OneHotEncoder(handle_unknown="ignore")),
                        ]
                    ),
                    categorical,
                ),
                (
                    "numeric",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="median")),
                            ("scaler", StandardScaler()),
                        ]
                    ),
                    numeric,
                ),
            ]
        )

        baseline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", LogisticRegression(max_iter=300)),
            ]
        )
        champion = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", RandomForestClassifier(n_estimators=140, max_depth=12, min_samples_leaf=4, random_state=42)),
            ]
        )

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
        baseline.fit(X_train, y_train)
        champion.fit(X_train, y_train)

        baseline_probs = baseline.predict_proba(X_test)[:, 1]
        probs = champion.predict_proba(X_test)[:, 1]
        threshold = 0.42
        preds = (probs >= threshold).astype(int)

        calibration_truth, calibration_pred = calibration_curve(y_test, probs, n_bins=8)
        rf_model: RandomForestClassifier = champion.named_steps["model"]
        feature_names = champion.named_steps["preprocessor"].get_feature_names_out()
        importance = sorted(
            zip(feature_names, rf_model.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )[:12]

        metrics = {
            "champion_model": "RandomForestClassifier",
            "baseline_model": "LogisticRegression",
            "auc": round(float(roc_auc_score(y_test, probs)), 3),
            "baseline_auc": round(float(roc_auc_score(y_test, baseline_probs)), 3),
            "precision": round(float(precision_score(y_test, preds)), 3),
            "recall": round(float(recall_score(y_test, preds)), 3),
            "f1": round(float(f1_score(y_test, preds)), 3),
            "confusion_matrix": confusion_matrix(y_test, preds).tolist(),
            "validation_rows": int(len(y_test)),
            "training_rows": int(len(y_train)),
            "decision_threshold": threshold,
        }

        self.artifacts = ModelArtifacts(
            model=champion,
            metrics=metrics,
            feature_importance=[
                {"feature": feature.replace("categorical__", "").replace("numeric__", ""), "importance": round(float(value), 4)}
                for feature, value in importance
            ],
            calibration=[
                {"predicted": round(float(pred), 3), "actual": round(float(actual), 3)}
                for actual, pred in zip(calibration_truth, calibration_pred)
            ],
        )
        return self.artifacts

    def score(self, shipments: pd.DataFrame) -> pd.DataFrame:
        if not self.artifacts:
            self.train(shipments)

        scored = shipments.copy()
        model_probability = self.artifacts.model.predict_proba(scored[FEATURE_COLUMNS])[:, 1]
        external_pressure = (
            0.32 * (scored["weather_severity_score"] / 100)
            + 0.24 * (scored["traffic_congestion_score"] / 100)
            + 0.18 * (scored["route_disruption_score"] / 100)
            + 0.12 * scored["road_closure_flag"]
            + 0.14 * scored["strike_alert_flag"]
        )
        operational_pressure = (
            0.24 * (scored["average_pick_queue_time"] / 100)
            + 0.22 * (scored["backlog_index"] / 100)
            + 0.2 * (1 - scored["staffing_level"])
            + 0.16 * scored["inventory_shortage_flag"]
        )
        scored["risk_probability"] = np.clip(0.62 * model_probability + 0.23 * external_pressure + 0.15 * operational_pressure, 0, 0.995)
        scored["risk_band"] = pd.cut(
            scored["risk_probability"],
            bins=[-0.01, 0.24, 0.38, 1.01],
            labels=["Low", "Medium", "High"],
        ).astype(str)
        driver_matrix = {
            "Warehouse backlog": scored["backlog_index"] * 0.25 + scored["average_pick_queue_time"] * 0.2,
            "Staffing strain": (1 - scored["staffing_level"]) * 100 + scored["absenteeism_rate"] * 80,
            "Carrier reliability": (1 - scored["carrier_on_time_pct"]) * 100 + scored["carrier_exception_rate"] * 60,
            "External disruption": scored["weather_severity_score"] * 0.5 + scored["traffic_congestion_score"] * 0.35 + scored["route_disruption_score"] * 0.4,
            "Inventory shortage": scored["inventory_shortage_flag"] * 100,
        }
        driver_frame = pd.DataFrame(driver_matrix)
        scored["key_risk_driver"] = driver_frame.idxmax(axis=1)
        scored["recommended_action"] = np.select(
            [
                scored["key_risk_driver"].eq("Warehouse backlog"),
                scored["key_risk_driver"].eq("Staffing strain"),
                scored["key_risk_driver"].eq("Carrier reliability"),
                scored["key_risk_driver"].eq("External disruption"),
            ],
            [
                "Re-sequence pick waves and add dock overflow capacity",
                "Add flex labor and prioritize critical shipments",
                "Shift freight to alternate carrier and escalate SLA review",
                "Pre-emptively reroute and expedite impacted shipments",
            ],
            default="Trigger exception review and inventory intervention",
        )
        scored["external_overlays"] = scored.apply(
            lambda row: [
                label
                for label, active in [
                    ("Weather", row["weather_severity_score"] > 55),
                    ("Traffic", row["traffic_congestion_score"] > 65),
                    ("Road Closure", row["road_closure_flag"] == 1),
                    ("Strike", row["strike_alert_flag"] == 1),
                    ("Holiday Peak", row["holiday_pressure_flag"] == 1),
                ]
                if active
            ],
            axis=1,
        )
        scored["risk_summary"] = (
            scored["key_risk_driver"]
            + " pressure at "
            + scored["origin_warehouse"]
            + " with "
            + scored["carrier"]
            + " exposure into "
            + scored["destination_region"]
        )
        return scored
