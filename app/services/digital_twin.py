from __future__ import annotations

from typing import Any

import networkx as nx
import pandas as pd


class DigitalTwinService:
    def build_network(self, scored: pd.DataFrame) -> dict[str, Any]:
        graph = nx.DiGraph()
        for warehouse in scored["origin_warehouse"].unique():
            graph.add_node(warehouse, kind="warehouse")
        for carrier in scored["carrier"].unique():
            graph.add_node(carrier, kind="carrier")
        for region in scored["destination_region"].unique():
            graph.add_node(region, kind="region")

        lane_frame = (
            scored.groupby(["origin_warehouse", "carrier", "destination_region"])
            .agg(volume=("shipment_id", "count"), avg_risk=("risk_probability", "mean"))
            .reset_index()
        )
        for row in lane_frame.itertuples():
            graph.add_edge(row.origin_warehouse, row.carrier, weight=int(row.volume), risk=float(row.avg_risk))
            graph.add_edge(row.carrier, row.destination_region, weight=int(row.volume), risk=float(row.avg_risk))

        nodes = []
        for node, attrs in graph.nodes(data=True):
            nodes.append({"id": node, "label": node, "kind": attrs.get("kind", "node")})
        edges = []
        for source, target, attrs in graph.edges(data=True):
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "weight": attrs.get("weight", 0),
                    "risk": round(float(attrs.get("risk", 0.0)), 3),
                }
            )
        return {"nodes": nodes, "edges": edges}
