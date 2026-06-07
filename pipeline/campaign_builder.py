"""Campaign segmentation, scheduling, and per-touch schedule generation."""
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta


def build_campaign_schedule(
    activation_actions: pd.DataFrame,
    retention_actions: pd.DataFrame,
    config: dict,
    run_date: datetime,
    output_dir: str = "outputs",
) -> pd.DataFrame:
    """
    Merge activation and retention action lists, assign campaign buckets,
    apply capacity constraints, and generate per-touch schedule rows.
    """
    pipeline_cfg = config.get("pipeline", {})
    max_emails = pipeline_cfg.get("max_emails_per_day", 200000)
    max_sms = pipeline_cfg.get("max_sms_per_day", 50000)
    max_calls = pipeline_cfg.get("max_calls_per_week", 5000)

    all_actions = pd.concat([
        activation_actions.assign(model_type="activation"),
        retention_actions.assign(model_type="retention"),
    ], ignore_index=True).sort_values("priority_score", ascending=False)

    # Assign campaign buckets
    if "offer_category" in all_actions.columns:
        all_actions["campaign_bucket"] = (
            all_actions["model_type"] + "_" +
            all_actions["risk_band"] + "_" +
            all_actions["offer_category"].fillna("general")
        )
    else:
        all_actions["campaign_bucket"] = all_actions["model_type"] + "_" + all_actions["risk_band"]

    # Apply channel capacity constraints (priority-sorted, top customers get constrained channels first)
    rm_count = 0
    sms_count = 0
    email_count = 0
    schedule_rows = []

    for _, row in all_actions.iterrows():
        cid = row["customer_id"]
        primary_ch = row.get("primary_channel", row.get("action_1_channel", "email"))
        secondary_ch = row.get("secondary_channel", "email")
        send_days_raw = row.get("action_1_send_days", "[1]")
        n_touches = int(row.get("action_1_frequency_touches", 1))

        # Downgrade channel if over capacity
        effective_channel = primary_ch
        if primary_ch == "crm_alert":
            if rm_count >= max_calls:
                effective_channel = "email"
            else:
                rm_count += 1
        elif primary_ch == "sms":
            if sms_count >= max_sms:
                effective_channel = "email"
            else:
                sms_count += 1

        # Parse send days
        try:
            send_days = json.loads(send_days_raw) if isinstance(send_days_raw, str) else send_days_raw
        except Exception:
            send_days = [1]

        # Generate one row per touch
        for touch_num, day_offset in enumerate(send_days[:n_touches], start=1):
            send_date = run_date + timedelta(days=int(day_offset))
            send_hour = int(row.get("send_hour_utc", 9))
            schedule_rows.append({
                "customer_id": cid,
                "campaign_id": f"{row.get('campaign_bucket', 'campaign')}_{run_date.strftime('%Y%m%d')}",
                "campaign_bucket": row.get("campaign_bucket", ""),
                "model_type": row.get("model_type", ""),
                "risk_band": row.get("risk_band", ""),
                "touch_number": touch_num,
                "scheduled_date": send_date.strftime("%Y-%m-%d"),
                "scheduled_hour_utc": send_hour,
                "channel": effective_channel,
                "template_id": f"{row.get('action_1_type', 'email')}_{effective_channel}",
                "offer_category": row.get("offer_category", "general"),
                "offer_type": row.get("offer_type", ""),
                "offer_value": row.get("offer_value", ""),
                "offer_expiry_date": row.get("offer_expiry_date", ""),
                "specific_action": row.get("specific_action", ""),
                "personalization_vars": row.get("personalization_vars", "{}"),
                "priority_score": row.get("priority_score", 0),
                "customer_segment": row.get("customer_segment", "standard"),
                "trigger_summary": row.get("trigger_summary", ""),
            })

    schedule_df = pd.DataFrame(schedule_rows).sort_values(
        ["scheduled_date", "priority_score"], ascending=[True, False]
    ).reset_index(drop=True)

    os.makedirs(output_dir, exist_ok=True)
    date_str = run_date.strftime("%Y-%m-%d")
    path = os.path.join(output_dir, f"campaign_schedule_{date_str}.csv")
    schedule_df.to_csv(path, index=False)
    print(f"Campaign schedule: {len(schedule_df):,} touches for {len(all_actions):,} customers → {path}")
    return schedule_df
