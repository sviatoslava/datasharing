"""Campaign event ingestion and feedback loop for next pipeline run."""
import pandas as pd
import os
import json
from datetime import datetime
from glob import glob


def ingest_campaign_events(
    events_dir: str,
    run_date: str,
) -> pd.DataFrame:
    """Load all campaign event files and return consolidated event log."""
    pattern = os.path.join(events_dir, "events_*.csv")
    files = glob(pattern)
    if not files:
        return pd.DataFrame(columns=["customer_id", "campaign_id", "event_type", "event_date"])
    dfs = [pd.read_csv(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


def compute_response_rates(events_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-campaign-bucket response rates from event log."""
    if len(events_df) == 0:
        return pd.DataFrame()
    redeemed = events_df[events_df["event_type"] == "offer_redeemed"]
    rates = redeemed.groupby("campaign_id").agg(
        n_redeemed=("customer_id", "count"),
    )
    sent = events_df[events_df["event_type"] == "sent"].groupby("campaign_id").agg(
        n_sent=("customer_id", "count"),
    )
    combined = rates.join(sent, how="outer").fillna(0)
    combined["redemption_rate"] = combined["n_redeemed"] / combined["n_sent"].clip(lower=1)
    return combined


def update_metadata(
    metadata_path: str,
    run_date: str,
    responded_customer_ids: set,
    performance_log: pd.DataFrame,
) -> None:
    os.makedirs(os.path.dirname(metadata_path) or ".", exist_ok=True)
    existing = {}
    if os.path.exists(metadata_path):
        with open(metadata_path) as f:
            existing = json.load(f)

    existing["last_run_date"] = run_date
    existing["responded_customer_ids"] = list(
        set(existing.get("responded_customer_ids", [])) | responded_customer_ids
    )

    with open(metadata_path, "w") as f:
        json.dump(existing, f, indent=2)


def run_feedback_ingestion(
    events_dir: str,
    metadata_path: str,
    run_date: str,
    output_dir: str = "outputs",
) -> dict:
    events_df = ingest_campaign_events(events_dir, run_date)
    if len(events_df) == 0:
        print("No campaign events found. Skipping feedback ingestion.")
        update_metadata(metadata_path, run_date, set(), pd.DataFrame())
        return {"n_events": 0, "n_responders": 0}

    redeemers = set(
        events_df[events_df["event_type"] == "offer_redeemed"]["customer_id"].unique()
    )
    rates = compute_response_rates(events_df)

    perf_path = os.path.join(output_dir, "campaign_performance_log.csv")
    if os.path.exists(perf_path):
        existing = pd.read_csv(perf_path)
        rates = pd.concat([existing, rates.reset_index()], ignore_index=True)
    else:
        rates = rates.reset_index()
    rates.to_csv(perf_path, index=False)

    update_metadata(metadata_path, run_date, redeemers, rates)
    print(f"Feedback ingested: {len(events_df):,} events, {len(redeemers):,} responders")
    return {"n_events": len(events_df), "n_responders": len(redeemers)}
