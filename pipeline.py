"""Prepare trade data for the Streamlit dashboard.

The code follows four ideas:
1. Read fictional trade events and reference tables.
2. Use SQL to keep each trade's latest event.
3. Check instruments, FX rates and amounts.
4. Return a trusted table and a separate list of issues.
"""

import sqlite3
from dataclasses import dataclass

import pandas as pd

from data_generator import AS_OF, make_reference_data, make_trade_events


# SQL uses ROW_NUMBER to select one version per trade.
# First: remove repeated deliveries of the SAME event ID.
# Then: select the newest version for every logical trade.
SNAPSHOT_SQL = """
WITH deliveries AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY event_id ORDER BY ingestion_timestamp DESC
    ) AS delivery_rank
    FROM raw_trade_events
),
deduplicated AS (
    SELECT * FROM deliveries WHERE delivery_rank = 1
),
versions AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY trade_id ORDER BY version DESC, event_timestamp DESC
    ) AS trade_rank
    FROM deduplicated
)
SELECT trade_id, event_id, version, business_date, event_timestamp, status,
       desk, instrument_id, currency, notional_local
FROM versions
WHERE trade_rank = 1
"""


# This just gathers our tables and numbers into one named result.
@dataclass
class Results:
    events: pd.DataFrame
    snapshot: pd.DataFrame
    active: pd.DataFrame
    evaluated: pd.DataFrame
    trusted: pd.DataFrame
    exceptions: pd.DataFrame
    instruments: pd.DataFrame
    fx_rates: pd.DataFrame
    legacy_eur: float
    trusted_eur: float
    cancelled_count: int
    duplicate_delivery_count: int
    amendment_count: int


def run_pipeline(resolve_chf=False, inject_duplicate=False):
    # 1. Create a small reproducible fictional dataset.
    events = make_trade_events().copy()
    instruments, fx_rates = make_reference_data()

    # These two choices are controlled by the app's checkboxes.
    if resolve_chf:
        chf_row = pd.DataFrame([{
            "business_date": AS_OF,
            "currency": "CHF",
            "units_per_eur": 0.94,  # Invented rate for this demo only.
        }])
        fx_rates = pd.concat([fx_rates, chf_row], ignore_index=True)

    if inject_duplicate:
        another_delivery = events.iloc[[0]].copy()
        another_delivery["ingestion_timestamp"] = "2026-10-09T21:00:00"
        events = pd.concat([events, another_delivery], ignore_index=True)

    # 2. Use a temporary SQLite database for one SQL transformation.
    connection = sqlite3.connect(":memory:")
    try:
        events.to_sql("raw_trade_events", connection, index=False)
        snapshot = pd.read_sql_query(SNAPSHOT_SQL, connection)
    finally:
        connection.close()

    # 3. Only booked trades can enter this reporting output.
    active = snapshot[snapshot["status"] == "BOOKED"].copy()

    # Add instrument information and the matching date/currency FX rate.
    active = active.merge(
        instruments[["instrument_id", "instrument_type"]],
        on="instrument_id", how="left", validate="many_to_one",
    )
    active = active.merge(
        fx_rates[["business_date", "currency", "units_per_eur"]],
        on=["business_date", "currency"], how="left", validate="many_to_one",
    )

    # Three easy-to-explain checks.
    active["invalid_instrument"] = active["instrument_type"].isna()
    active["missing_fx"] = active["units_per_eur"].isna()
    active["invalid_amount"] = active["notional_local"] <= 0

    quality_columns = ["invalid_instrument", "missing_fx", "invalid_amount"]
    active["eligible"] = ~active[quality_columns].any(axis=1)

    # Our rate means foreign currency units for one euro.
    # Dividing gives the euro equivalent. Missing FX gives NaN, not zero.
    active["notional_eur"] = active["notional_local"] / active["units_per_eur"]

    evaluated = active.copy()
    trusted = evaluated[evaluated["eligible"]].copy()
    exceptions = evaluated[~evaluated["eligible"]].copy()

    # Write a straightforward explanation for each rejected trade.
    issue_descriptions = []
    suggested_owners = []
    for _, row in exceptions.iterrows():
        issues = []
        if row["invalid_instrument"]:
            issues.append("Unknown instrument")
        if row["missing_fx"]:
            issues.append("Missing FX rate")
        if row["invalid_amount"]:
            issues.append("Non-positive notional")

        description = "; ".join(issues)
        issue_descriptions.append(description)

        if "FX" in description:
            suggested_owners.append("Market Data")
        elif "instrument" in description:
            suggested_owners.append("Reference Data")
        else:
            suggested_owners.append("Trade Operations")

    exceptions["issue"] = issue_descriptions
    exceptions["owner"] = suggested_owners
    exceptions["resolution_status"] = "Open (synthetic example)"

    # 4. Compare two reporting approaches.
    # This is deliberately an INCORRECT control-free total for teaching.
    # It counts inbound rows even when older, cancelled or duplicated.
    uncontrolled_rows = events.merge(
        fx_rates, on=["business_date", "currency"],
        how="left", validate="many_to_one",
    )
    uncontrolled_eur = uncontrolled_rows["notional_local"] / uncontrolled_rows["units_per_eur"]
    legacy_eur = float(uncontrolled_eur.sum(skipna=True))

    # The trusted total only includes eligible latest booked trades.
    trusted_eur = float(trusted["notional_eur"].sum())

    cancelled_count = int((snapshot["status"] == "CANCELLED").sum())
    duplicate_count = int(len(events) - events["event_id"].nunique())
    amendment_count = int((snapshot["version"] > 1).sum())

    return Results(
        events=events,
        snapshot=snapshot,
        active=active,
        evaluated=evaluated,
        trusted=trusted,
        exceptions=exceptions,
        instruments=instruments,
        fx_rates=fx_rates,
        legacy_eur=legacy_eur,
        trusted_eur=trusted_eur,
        cancelled_count=cancelled_count,
        duplicate_delivery_count=duplicate_count,
        amendment_count=amendment_count,
    )
