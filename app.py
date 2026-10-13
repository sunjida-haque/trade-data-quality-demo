"""A simple Streamlit dashboard for checking fictional trade data.

Run from this folder with: python -m streamlit run app.py
The data processing is in pipeline.py so the dashboard stays easy to read.
"""

import pandas as pd
import streamlit as st

from pipeline import run_pipeline, SNAPSHOT_SQL


# PAGE DESIGN: almost everything comes from .streamlit/config.toml.
# Just one small rule makes the selected tab bold and blue.
st.set_page_config(page_title="Trade Data Quality", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"] {
        padding-top: 1rem !important;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        font-weight: 700 !important;
        color: #19588D !important;
    }
    [data-baseweb="tab-highlight"] {
        background-color: #19588D !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# STEP 1: Let the user change two examples in the fictional input data.
with st.sidebar:
    st.subheader("Change input data and rerun checks")
    resolve_chf = st.checkbox("Add a missing CHF exchange rate")
    add_duplicate = st.checkbox("Add a repeated trade message")


# STEP 2: Run the same processing rules after any input change.
result = run_pipeline(resolve_chf=resolve_chf, inject_duplicate=add_duplicate)
active_trades = len(result.active)
eligible_trades = len(result.trusted)

if active_trades > 0:
    eligible_percent = 100 * eligible_trades / active_trades
else:
    eligible_percent = 0


# STEP 3: Explain the business question and provide three short sections.
st.markdown(
    "<h1 style='text-align: center;'>Trade Data Quality</h1>",
    unsafe_allow_html=True
)
st.write(
    "**Business question:** Why can two reports show different EUR totals "
    "for the same trade data? This example compares the raw event totals "
    "with a checked, trade-level report."
)

report_tab, quality_tab, trace_tab = st.tabs(
    ["Reporting overview", "Data checks & ownership", "Definitions & traceability"]
)


# TAB 1: Show the reporting difference and a simple chart.
with report_tab:
    st.subheader("Compare the two reporting totals")

    uncontrolled_millions = result.legacy_eur / 1_000_000
    validated_millions = result.trusted_eur / 1_000_000
    difference_millions = uncontrolled_millions - validated_millions

    # Each figure is on its own line rather than in three side-by-side cards.
    st.write(f"**Uncontrolled total:** €{uncontrolled_millions:,.2f} million")
    st.write(f"**Validated total:** €{validated_millions:,.2f} million")
    st.write(f"**Difference:** €{difference_millions:,.2f} million")

    st.write(
        "**Uncontrolled:** Adds each incoming event with an available FX rate, "
        "including older versions, cancelled events and repeat deliveries."
    )
    st.write(
        "**Validated:** Counts the most recent booked version of each trade "
        "only when the instrument, amount and FX rate pass the checks."
    )
    st.write("**Meaning:** This is a reporting discrepancy, not a financial loss.")

    st.divider()
    st.subheader("The validated reporting output")

    left_column, right_column = st.columns([1.2, 1])
    with left_column:
        st.write("**EUR notional by trading desk**")
        desk_totals = result.trusted.groupby("desk")["notional_eur"].sum()
        desk_totals = desk_totals / 1_000_000
        desk_totals = desk_totals.sort_values(ascending=False)
        desk_totals.name = "EUR million"
        st.bar_chart(desk_totals, height=260, color="#19588D")

    with right_column:
        st.write("**Published dataset: what it means**")
        st.write("**One row:** one eligible, latest booked trade.")
        st.write("**EUR amount:** local notional divided by FX units per EUR.")
        st.write("**Not included:** cancelled or invalid trades.")
        st.write("**Intended use:** a consistent starting table for business reporting.")


# TAB 2: Show the data rules and the records that failed.
with quality_tab:
    st.subheader("Data checks and ownership")

    st.write(f"**Active trades:** {active_trades:,}")
    st.write(f"**Eligible trades:** {eligible_trades:,}")
    st.write(f"**Eligibility rate:** {eligible_percent:.1f}%")
    st.write(
        f"**Trade lifecycle:** {result.cancelled_count} cancelled latest-version trades "
        f"and {result.duplicate_delivery_count} repeated event deliveries."
    )

    st.write("**Quality rules**")
    quality_rules = [
        {
            "Data element": "Instrument ID",
            "Rule": "Exists in instrument reference data",
            "Why it matters": "An unknown instrument cannot be described reliably",
            "Failed": int(result.evaluated["invalid_instrument"].sum()),
            "Suggested owner": "Reference Data",
        },
        {
            "Data element": "FX rate",
            "Rule": "Available for the trade date and currency",
            "Why it matters": "A EUR conversion needs a matching rate",
            "Failed": int(result.evaluated["missing_fx"].sum()),
            "Suggested owner": "Market Data",
        },
        {
            "Data element": "Trade amount",
            "Rule": "Greater than zero",
            "Why it matters": "Gross booked notional must be positive",
            "Failed": int(result.evaluated["invalid_amount"].sum()),
            "Suggested owner": "Trade Operations",
        },
    ]
    st.dataframe(pd.DataFrame(quality_rules), hide_index=True, use_container_width=True)

    st.write("**Exception register: records needing review**")
    if result.exceptions.empty:
        st.write("No active data-quality exceptions in this example.")
    else:
        exception_columns = [
            "trade_id", "desk", "instrument_id", "currency",
            "issue", "owner", "resolution_status",
        ]
        exceptions_table = result.exceptions[exception_columns].copy()
        exceptions_table = exceptions_table.rename(columns={
            "trade_id": "Trade ID",
            "desk": "Desk",
            "instrument_id": "Instrument",
            "currency": "Currency",
            "issue": "Issue",
            "owner": "Suggested owner",
            "resolution_status": "Status",
        })
        st.dataframe(exceptions_table, hide_index=True, use_container_width=True)


# TAB 3: A few definitions, then the history of one selected trade.
with trace_tab:
    st.subheader("Definitions and traceability")

    definitions = [
        ["Trade ID", "Identifier for one logical trade", "Trade Operations"],
        ["Latest trade version", "Highest version after repeated deliveries are removed", "Trade Operations"],
        ["Booked trade", "Trade whose latest status is BOOKED", "Trade Operations"],
        ["EUR gross booked notional", "Eligible local notional converted using the matching FX rate", "Business Reporting"],
        ["Eligible trade", "Booked, known instrument, positive amount and valid FX", "Data Management"],
    ]
    glossary = pd.DataFrame(
        definitions,
        columns=["Business term", "Definition in this project", "Suggested owner"],
    )
    st.dataframe(glossary, hide_index=True, use_container_width=True)

    st.write("**Follow one trade through the process**")
    trade_ids = sorted(result.events["trade_id"].unique())
    first_trade = trade_ids.index("TRD-0024") if "TRD-0024" in trade_ids else 0
    chosen_trade = st.selectbox("Trade ID", trade_ids, index=first_trade)

    trade_history = result.events[result.events["trade_id"] == chosen_trade]
    latest_trade = result.snapshot[result.snapshot["trade_id"] == chosen_trade]
    checked_trade = result.evaluated[result.evaluated["trade_id"] == chosen_trade]

    if not latest_trade.empty:
        latest_row = latest_trade.iloc[0]
        st.write(f"**Latest status:** {latest_row['status']}")
        st.write(f"**Selected version:** {int(latest_row['version'])}")
        st.write(f"**Incoming event rows:** {len(trade_history)}")

    if not checked_trade.empty:
        checked_row = checked_trade.iloc[0]
        if checked_row["eligible"]:
            st.write(
                f"**Eligible for reporting:** €{checked_row['notional_eur']:,.2f} "
                "is included in the validated total."
            )
        else:
            problem_rows = result.exceptions[
                result.exceptions["trade_id"] == chosen_trade
            ]
            if not problem_rows.empty:
                reason = problem_rows.iloc[0]["issue"]
            else:
                reason = "Failed a data-quality rule"
            st.write(f"**Not eligible:** {reason}.")
    elif not latest_trade.empty:
        st.write("**Not included:** The latest status is not BOOKED.")

    event_columns = [
        "event_id", "version", "status", "currency",
        "notional_local", "ingestion_timestamp",
    ]
    history_table = trade_history[event_columns].copy()
    history_table = history_table.rename(columns={
        "event_id": "Event",
        "version": "Version",
        "status": "Status",
        "currency": "Currency",
        "notional_local": "Local notional",
        "ingestion_timestamp": "Received at",
    })
    st.dataframe(history_table, hide_index=True, use_container_width=True)

    # Plain text instead of a shaded box, tooltip or decorative warning.
    st.write(
        "**Trace:** Incoming events → remove repeated deliveries → "
        "select latest trade version → check data → "
        "validated EUR total or exception register."
    )

    with st.expander("Technical details: SQL and sample data"):
        st.code(SNAPSHOT_SQL, language="sql")
        st.write("**Sample of the validated dataset**")
        sample_columns = [
            "trade_id", "desk", "instrument_type", "currency",
            "notional_local", "units_per_eur", "notional_eur",
        ]
        sample_data = result.trusted[sample_columns].head(20)
        st.dataframe(sample_data, hide_index=True, use_container_width=True)
        csv_data = result.trusted[sample_columns].to_csv(index=False)
        st.download_button(
            "Download sample data (CSV)", csv_data,
            file_name="sample_validated_trades.csv", mime="text/csv",
        )
