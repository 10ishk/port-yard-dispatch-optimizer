"""Streamlit dashboard for the Port Yard Dispatch Optimizer."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SHIPMENTS, DEFAULT_VEHICLES, get_database_path  # noqa: E402
from src.cost_model import as_datetime  # noqa: E402
from src.database import has_input_data, load_table, write_base_dataset  # noqa: E402
from src.generate_synthetic_data import generate_dataset  # noqa: E402
from src.optimize_routes import optimize_dispatch  # noqa: E402


st.set_page_config(
    page_title="Port Yard Dispatch Optimizer",
    page_icon="PY",
    layout="wide",
)


def _ensure_data() -> None:
    db_path = get_database_path()
    if not has_input_data(db_path):
        shipments, vehicles, nodes = generate_dataset(DEFAULT_SHIPMENTS, DEFAULT_VEHICLES)
        write_base_dataset(shipments, vehicles, nodes, db_path)


def _ensure_plan() -> None:
    _ensure_data()
    if load_table("optimization_runs").empty:
        optimize_dispatch(export_csv=False)


@st.cache_data(ttl=20)
def load_dashboard_data() -> dict[str, pd.DataFrame]:
    _ensure_plan()
    return {
        "shipments": load_table("shipments"),
        "vehicles": load_table("vehicles"),
        "nodes": load_table("nodes"),
        "dispatch": load_table("dispatch_plan"),
        "summary": load_table("route_summary"),
        "unassigned": load_table("unassigned_shipments"),
        "runs": load_table("optimization_runs"),
    }


def clear_data_cache() -> None:
    load_dashboard_data.clear()


def metric_row(data: dict[str, pd.DataFrame]) -> None:
    shipments = data["shipments"]
    vehicles = data["vehicles"]
    dispatch = data["dispatch"]
    summary = data["summary"]
    unassigned = data["unassigned"]
    runs = data["runs"]
    latest = runs.iloc[0] if not runs.empty else {}
    cols = st.columns(8)
    cols[0].metric("Shipments", f"{len(shipments):,}")
    cols[1].metric("Assigned", f"{int(latest.get('assigned_shipments', len(dispatch))):,}")
    cols[2].metric("Unassigned", f"{len(unassigned):,}")
    cols[3].metric("Active Vehicles", f"{int(vehicles['active_flag'].sum()) if not vehicles.empty else 0:,}")
    cols[4].metric("Avg Utilization", f"{float(latest.get('vehicle_utilization_avg', 0.0)):.1f}%")
    cols[5].metric("Route Cost", f"{float(latest.get('total_cost', 0.0)):,.0f}")
    cols[6].metric("SLA Risks", f"{int(latest.get('sla_risk_count', 0)):,}")
    critical = len(dispatch[dispatch["sla_risk_category"] == "Critical"]) if not dispatch.empty else 0
    cols[7].metric("Critical", f"{critical:,}")


def page_overview(data: dict[str, pd.DataFrame]) -> None:
    st.title("Dispatch Overview")
    metric_row(data)
    shipments = data["shipments"]
    summary = data["summary"]
    dispatch = data["dispatch"]
    left, right = st.columns(2)
    with left:
        priority_counts = shipments["priority"].value_counts().reset_index()
        priority_counts.columns = ["priority", "shipments"]
        st.plotly_chart(
            px.bar(priority_counts, x="priority", y="shipments", color="priority"),
            use_container_width=True,
        )
        if not dispatch.empty:
            risk_counts = dispatch["sla_risk_category"].value_counts().reset_index()
            risk_counts.columns = ["risk", "shipments"]
            st.plotly_chart(
                px.pie(risk_counts, names="risk", values="shipments", hole=0.42),
                use_container_width=True,
            )
    with right:
        if not summary.empty:
            st.plotly_chart(
                px.bar(
                    summary,
                    x="vehicle_id",
                    y=["utilization_kg_pct", "utilization_cbm_pct"],
                    barmode="group",
                ),
                use_container_width=True,
            )
            st.plotly_chart(
                px.bar(summary, x="vehicle_id", y="total_cost", color="vehicle_type"),
                use_container_width=True,
            )


def page_planner(data: dict[str, pd.DataFrame]) -> None:
    st.title("Optimization Planner")
    with st.form("planner_form"):
        col1, col2, col3, col4 = st.columns(4)
        shipments_count = col1.number_input("Shipments", min_value=10, max_value=2000, value=120, step=10)
        vehicles_count = col2.number_input("Vehicles", min_value=1, max_value=250, value=16, step=1)
        max_hours = col3.slider("Max Route Hours", min_value=1.0, max_value=14.0, value=8.0, step=0.5)
        mode = col4.selectbox(
            "Mode",
            ["balanced", "minimize_cost", "minimize_delay", "maximize_utilization"],
            index=0,
        )
        col5, col6, col7 = st.columns(3)
        include_priority_only = col5.checkbox("Priority Only")
        force_fallback = col6.checkbox("Force Fallback")
        congestion_factor = col7.slider("Congestion", min_value=0.5, max_value=2.5, value=1.0, step=0.1)
        submitted = st.form_submit_button("Run Optimization")

    if submitted:
        result = optimize_dispatch(
            optimization_mode=mode,
            max_route_duration_hours=max_hours,
            include_priority_only=include_priority_only,
            congestion_factor=congestion_factor,
            force_fallback=force_fallback,
            regenerate_data=True,
            generated_shipments=int(shipments_count),
            generated_vehicles=int(vehicles_count),
            export_csv=True,
        )
        clear_data_cache()
        st.success(f"Created {result['plan_id']} with {result['engine']} engine.")
        data = load_dashboard_data()

    metric_row(data)
    st.subheader("Dispatch Plan")
    st.dataframe(data["dispatch"], use_container_width=True, hide_index=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Route Summary")
        st.dataframe(data["summary"], use_container_width=True, hide_index=True)
    with col2:
        st.subheader("Unassigned Shipments")
        st.dataframe(data["unassigned"], use_container_width=True, hide_index=True)


def _route_color(index: int) -> str:
    colors = [
        "blue",
        "green",
        "red",
        "purple",
        "orange",
        "darkred",
        "cadetblue",
        "darkgreen",
        "darkblue",
    ]
    return colors[index % len(colors)]


def page_map(data: dict[str, pd.DataFrame]) -> None:
    st.title("Route Map")
    dispatch = data["dispatch"]
    shipments = data["shipments"]
    vehicles = data["vehicles"]
    nodes = data["nodes"].set_index("node_id", drop=False)
    if dispatch.empty:
        st.info("No dispatch plan is available yet.")
        return

    merged = dispatch.merge(
        shipments[["shipment_id", "destination_node", "priority", "waybill_number"]],
        on="shipment_id",
        how="left",
    )
    center = [float(data["nodes"]["latitude"].mean()), float(data["nodes"]["longitude"].mean())]
    route_map = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")
    for vehicle_index, (vehicle_id, stops) in enumerate(merged.groupby("vehicle_id")):
        vehicle = vehicles[vehicles["vehicle_id"] == vehicle_id].iloc[0]
        start = nodes.loc[str(vehicle["start_node"])]
        color = _route_color(vehicle_index)
        coordinates = [[float(start["latitude"]), float(start["longitude"])]]
        folium.Marker(
            location=coordinates[0],
            popup=f"{vehicle_id} start: {start['node_name']}",
            icon=folium.Icon(color=color, icon="home"),
        ).add_to(route_map)
        for _, stop in stops.sort_values("stop_sequence").iterrows():
            node = nodes.loc[str(stop["destination_node"])]
            location = [float(node["latitude"]), float(node["longitude"])]
            coordinates.append(location)
            folium.Marker(
                location=location,
                popup=f"{vehicle_id} stop {int(stop['stop_sequence'])}: {stop['waybill_number']}",
                icon=folium.DivIcon(
                    html=(
                        "<div style='font-size:12px;font-weight:700;color:white;"
                        f"background:{color};border-radius:12px;width:24px;height:24px;"
                        "text-align:center;line-height:24px;'>"
                        f"{int(stop['stop_sequence'])}</div>"
                    )
                ),
            ).add_to(route_map)
        if len(coordinates) > 1:
            folium.PolyLine(coordinates, color=color, weight=4, opacity=0.72).add_to(route_map)
    components.html(route_map._repr_html_(), height=680)


def page_risks(data: dict[str, pd.DataFrame]) -> None:
    st.title("SLA Risk and Exceptions")
    dispatch = data["dispatch"]
    shipments = data["shipments"]
    if dispatch.empty:
        st.info("No dispatch plan is available yet.")
        return
    risks = dispatch[
        dispatch["sla_risk_category"].isin(["High", "Critical"]) | (dispatch["expected_late_flag"] == 1)
    ].merge(
        shipments[
            [
                "shipment_id",
                "waybill_number",
                "priority",
                "promised_delivery_time",
                "latest_delivery_time",
                "penalty_if_late",
            ]
        ],
        on="shipment_id",
        how="left",
    )
    st.dataframe(
        risks[
            [
                "shipment_id",
                "waybill_number",
                "priority",
                "vehicle_id",
                "planned_arrival",
                "promised_delivery_time",
                "expected_late_flag",
                "sla_risk_score",
                "sla_risk_category",
                "risk_reason",
                "suggested_action",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _urgent_shipment(nodes: pd.DataFrame, service_level: str) -> pd.DataFrame:
    destination = nodes[nodes["node_type"].isin(["Customer", "Warehouse"])].iloc[0]
    now = pd.Timestamp("2026-01-15T09:00")
    weight = 240.0 if service_level != "Heavy Cargo" else 1600.0
    volume = 1.2 if service_level != "Heavy Cargo" else 7.5
    return pd.DataFrame(
        [
            {
                "shipment_id": "SHP-URGENT-001",
                "waybill_number": "WBURGENT001",
                "customer_id": "CUS-URGENT",
                "priority": "Critical",
                "origin_node": "NODE-001",
                "destination_node": destination["node_id"],
                "destination_lat": float(destination["latitude"]),
                "destination_lon": float(destination["longitude"]),
                "weight_kg": weight,
                "volume_cbm": volume,
                "service_type": service_level,
                "earliest_delivery_time": now.isoformat(timespec="minutes"),
                "latest_delivery_time": (now + timedelta(hours=3)).isoformat(timespec="minutes"),
                "promised_delivery_time": (now + timedelta(hours=2, minutes=30)).isoformat(timespec="minutes"),
                "handling_type": "Normal" if service_level != "Heavy Cargo" else "Heavy",
                "revenue": 850.0,
                "penalty_if_late": 500.0,
                "status": "Pending",
                "created_at": (now - timedelta(hours=1)).isoformat(timespec="minutes"),
            }
        ]
    )


def page_what_if(data: dict[str, pd.DataFrame]) -> None:
    st.title("What-if Simulation")
    shipments = data["shipments"].copy()
    vehicles = data["vehicles"].copy()
    nodes = data["nodes"].copy()
    with st.form("what_if_form"):
        col1, col2, col3 = st.columns(3)
        add_urgent = col1.checkbox("Add Urgent Shipment", value=True)
        removed_vehicle = col2.selectbox("Remove Vehicle", ["None"] + list(vehicles["vehicle_id"]))
        capacity_reduction = col3.slider("Capacity Reduction", min_value=0, max_value=50, value=0, step=5)
        col4, col5, col6 = st.columns(3)
        congestion = col4.slider("Congestion", min_value=0.5, max_value=2.5, value=1.25, step=0.1)
        service_level = col5.selectbox("Urgent Service", ["Express", "Standard", "Heavy Cargo"], index=0)
        mode = col6.selectbox("Mode", ["balanced", "minimize_cost", "minimize_delay", "maximize_utilization"])
        submitted = st.form_submit_button("Run Simulation")

    if not submitted:
        return

    if add_urgent:
        shipments = pd.concat([shipments, _urgent_shipment(nodes, service_level)], ignore_index=True)
    if removed_vehicle != "None":
        vehicles.loc[vehicles["vehicle_id"] == removed_vehicle, "active_flag"] = 0
    if capacity_reduction:
        factor = 1.0 - (capacity_reduction / 100.0)
        vehicles["capacity_kg"] = vehicles["capacity_kg"] * factor
        vehicles["capacity_cbm"] = vehicles["capacity_cbm"] * factor

    result = optimize_dispatch(
        optimization_mode=mode,
        max_route_duration_hours=8.0,
        include_priority_only=False,
        congestion_factor=congestion,
        shipments=shipments,
        vehicles=vehicles,
        nodes=nodes,
        persist=False,
        export_csv=False,
    )
    run = result["run_summary"].iloc[0]
    cols = st.columns(6)
    cols[0].metric("Assigned", int(run["assigned_shipments"]))
    cols[1].metric("Unassigned", int(run["unassigned_shipments"]))
    cols[2].metric("Cost", f"{float(run['total_cost']):,.0f}")
    cols[3].metric("SLA Risks", int(run["sla_risk_count"]))
    cols[4].metric("Utilization", f"{float(run['vehicle_utilization_avg']):.1f}%")
    cols[5].metric("Engine", str(run["engine"]))
    st.dataframe(result["dispatch_plan"], use_container_width=True, hide_index=True)
    st.dataframe(result["unassigned_shipments"], use_container_width=True, hide_index=True)


def main() -> None:
    st.sidebar.title("Port Yard Dispatch")
    if st.sidebar.button("Refresh"):
        clear_data_cache()
    page = st.sidebar.radio(
        "View",
        [
            "Dispatch Overview",
            "Optimization Planner",
            "Route Map",
            "SLA Risk and Exceptions",
            "What-if Simulation",
        ],
    )
    data = load_dashboard_data()
    if page == "Dispatch Overview":
        page_overview(data)
    elif page == "Optimization Planner":
        page_planner(data)
    elif page == "Route Map":
        page_map(data)
    elif page == "SLA Risk and Exceptions":
        page_risks(data)
    else:
        page_what_if(data)


if __name__ == "__main__":
    main()

