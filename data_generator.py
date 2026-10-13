"""Deterministic synthetic finance datasets. No employer or customer data."""
from __future__ import annotations
import random
from datetime import datetime, timedelta
import pandas as pd

AS_OF = "2026-10-09"


def make_reference_data():
    instruments = pd.DataFrame([
        {"instrument_id": f"INS-{i:03}", "instrument_type": typ, "description": f"Synthetic {typ} {i:03}"}
        for i, typ in enumerate((["Bond", "Equity", "Swap", "ETF", "FX Forward"] * 6), start=1)
    ])
    # Foreign currency units for EUR 1; divide local notional by this rate.
    fx = pd.DataFrame([
        {"business_date": AS_OF, "currency": c, "units_per_eur": rate}
        for c, rate in [("EUR", 1.0), ("USD", 1.18), ("GBP", 0.86), ("SEK", 10.80)]
    ])
    return instruments, fx


def make_trade_events() -> pd.DataFrame:
    rng = random.Random(11027)
    event_rows = []
    booked_at = datetime(2026,10,9,7,30)
    desks = ["Rates", "Equities", "Credit"]
    currencies = ["EUR", "USD", "GBP", "SEK"]
    cancel_ids = {7, 34, 68, 105, 130, 151}
    amended_ids = {9, 19, 27, 40, 52, 65, 83, 95, 112, 127, 145, 159}
    unknown_instrument_ids = {18, 45, 86, 119}
    missing_fx_ids = {24, 58, 92, 117, 154}
    invalid_amount_ids = {13, 71, 109, 137}
    # These sets are deliberately disjoint; each data-quality error has one primary cause.
    for i in range(1, 161):
        ccy = rng.choice(currencies)
        if i in missing_fx_ids:
            ccy = "CHF"  # Not in the starting FX reference dataset.
        notional = rng.choice([450_000, 720_000, 950_000, 1_250_000, 1_800_000, 2_150_000, 2_800_000])
        if i in invalid_amount_ids:
            notional = -notional if i % 2 else 0
        row = {
            "trade_id": f"TRD-{i:04}",
            "event_id": f"EVT-{i:04}-1",
            "version": 1,
            "event_timestamp": (booked_at+timedelta(minutes=2*i)).isoformat(timespec="seconds"),
            "ingestion_timestamp": (booked_at+timedelta(minutes=2*i, seconds=12)).isoformat(timespec="seconds"),
            "business_date": AS_OF,
            "status": "BOOKED",
            "desk": desks[i % 3],
            "instrument_id": "INS-999" if i in unknown_instrument_ids else f"INS-{(i%30)+1:03}",
            "currency": ccy,
            "notional_local": float(notional),
            "source": "MARKETS_GATEWAY",
        }
        event_rows.append(row)
        if i in amended_ids or i in cancel_ids:
            newer = dict(row)
            newer["event_id"] = f"EVT-{i:04}-2"
            newer["version"] = 2
            newer["event_timestamp"] = (booked_at+timedelta(minutes=2*i+1)).isoformat(timespec="seconds")
            newer["ingestion_timestamp"] = (booked_at+timedelta(minutes=2*i+1, seconds=12)).isoformat(timespec="seconds")
            if i in cancel_ids:
                newer["status"] = "CANCELLED"
            else:
                newer["notional_local"] = float(round(notional*1.15,2))
            event_rows.append(newer)
    # Exactly five duplicate *deliveries* of the same event_id: not five legitimate trades.
    for i in [6, 25, 63, 96, 125]:
        copied = next(r.copy() for r in event_rows if r["trade_id"]==f"TRD-{i:04}" and r["version"]==1)
        copied["ingestion_timestamp"] = (datetime.fromisoformat(copied["ingestion_timestamp"])+timedelta(hours=1)).isoformat(timespec="seconds")
        event_rows.append(copied)
    return pd.DataFrame(event_rows)

if __name__ == "__main__":
    print(make_trade_events().head())
