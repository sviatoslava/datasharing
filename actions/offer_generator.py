"""Personalized offer generation: specific category + specific action + timing + channel."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


OFFER_VALUE_TABLE = {
    # (segment, risk_band) -> (offer_type, value_spec, duration_days)
    ("premium", "high_risk"):   ("cashback", 0.10, 60),
    ("premium", "medium_risk"): ("cashback", 0.05, 30),
    ("premium", "low_risk"):    ("points_multiplier", 3, 30),
    ("standard", "high_risk"):  ("cashback", 0.07, 60),
    ("standard", "medium_risk"):("cashback", 0.04, 30),
    ("standard", "low_risk"):   ("points_multiplier", 2, 30),
    ("student", "high_risk"):   ("statement_credit", 10, 30),
    ("student", "medium_risk"): ("statement_credit", 5, 30),
    ("student", "low_risk"):    ("bonus_points", 500, 30),
}

SPEND_THRESHOLDS = {"premium": 200, "standard": 100, "student": 50}
FREQ_BY_RISK = {"high_risk": 3, "medium_risk": 2, "low_risk": 1}

CHANNEL_PEAK_HOURS = {
    "mobile_app": 19, "web": 13, "POS": 12, "ATM": 12,
    "push_notification": 19, "sms": 10, "email": 9, "in_app_banner": -1,
}

CHANNEL_PEAK_DAYS = {
    "mobile_app": 5,   # Saturday
    "POS": 6,          # Sunday
    "ATM": 4,          # Friday
    "web": 1,          # Tuesday
    "email": 1,        # Tuesday
    "push_notification": 5,
    "sms": 2,          # Wednesday
}


def _render_offer_action(
    offer_category: str,
    segment: str,
    risk_band: str,
    favorite_merchant: str,
    offer_duration_days: int,
    offer_type: str,
    offer_value,
    templates: dict,
) -> str:
    n_times = FREQ_BY_RISK.get(risk_band, 1)
    threshold = SPEND_THRESHOLDS.get(segment, 100)
    template = templates.get(offer_category, templates.get("general", "{offer_category}:{offer_type}"))

    merchant = favorite_merchant if favorite_merchant not in ["unknown", ""] else "any retailer"

    if offer_type == "cashback":
        reward = f"{int(offer_value * 100)}pct_cashback"
        savings = round(threshold * offer_value, 2)
    elif offer_type == "points_multiplier":
        reward = f"{offer_value}x_points"
        savings = 0
    elif offer_type == "statement_credit":
        reward = f"${offer_value}_credit"
        savings = offer_value
    else:
        reward = f"{offer_value}_bonus_points"
        savings = 0

    try:
        rendered = template.format(
            merchant=merchant,
            threshold=threshold,
            window=offer_duration_days,
            reward=reward,
            n_times=n_times,
            multiplier=offer_value if offer_type == "points_multiplier" else 3,
            savings=savings,
            credit=offer_value if offer_type == "statement_credit" else 5,
            points=offer_value if offer_type == "bonus_points" else 500,
            cashback=int(offer_value * 100) if isinstance(offer_value, float) else 5,
            offer_category=offer_category,
            offer_type=offer_type,
        )
    except (KeyError, ValueError):
        rendered = f"{offer_category}:use_card_{n_times}x_earn_{reward}_in_{offer_duration_days}d"

    return rendered


def _select_offer_channel(preferred_channel: str, digital_adoption: float) -> tuple:
    """Returns (primary_channel, secondary_channel)."""
    if preferred_channel in ["mobile_app", "web"] and digital_adoption >= 0.4:
        return "push_notification", "in_app_banner"
    elif preferred_channel in ["POS"] and digital_adoption < 0.2:
        return "sms", "email"
    elif preferred_channel == "ATM":
        return "sms", "email"
    else:
        return "email", "push_notification"


def _compute_send_schedule(
    primary_channel: str,
    preferred_channel: str,
    send_days: list,
    run_date: datetime,
) -> tuple:
    """Returns (send_hour_utc, send_day_of_week, scheduled_send_1)."""
    send_hour = CHANNEL_PEAK_HOURS.get(primary_channel, 9)
    if send_hour == -1:
        send_hour = 9  # in_app_banner is event-driven; use 9am for scheduling purposes
    send_day_of_week = CHANNEL_PEAK_DAYS.get(preferred_channel, 1)

    # First actual send date: next occurrence of peak_day_of_week
    days_ahead = (send_day_of_week - run_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    first_send_date = run_date + timedelta(days=days_ahead)
    first_send_date = first_send_date.replace(hour=send_hour, minute=0)
    return send_hour, send_day_of_week, first_send_date.strftime("%Y-%m-%d %H:%M")


def generate_offers(
    actions_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    txn_df: pd.DataFrame,
    config: dict,
    run_date: datetime,
    mcc_group_map: dict,
) -> pd.DataFrame:
    """
    Generate personalized offers for each customer in actions_df.
    Returns actions_df enriched with offer columns.
    """
    templates = config["actions"]["offer_action_templates"]
    spend_thresholds = config["actions"]["spend_threshold_by_segment"]

    # Precompute favorite merchant per customer per dominant group
    txn_recent = txn_df[
        txn_df["transaction_date"] >= run_date - timedelta(days=90)
    ].copy()
    txn_recent["mcc_group"] = txn_recent["merchant_category_code"].map(mcc_group_map).fillna("other")

    def get_favorite_merchant(cid, group):
        sub = txn_recent[
            (txn_recent["customer_id"] == cid) &
            (txn_recent["mcc_group"] == group)
        ]
        if len(sub) == 0:
            return "unknown"
        return sub["merchant_name"].mode().iloc[0]

    # Merge scores metadata
    score_cols = ["customer_id", "preferred_channel", "customer_segment"]
    if "digital_adoption" in scores_df.columns:
        score_cols.append("digital_adoption")
    elif "digital_adoption_30d" in scores_df.columns:
        score_cols.append("digital_adoption_30d")
    if "dominant_mcc_group" in scores_df.columns:
        score_cols.append("dominant_mcc_group")

    merged = actions_df.merge(scores_df[score_cols], on="customer_id", how="left", suffixes=("", "_score"))

    rows = []
    for _, row in merged.iterrows():
        cid = row["customer_id"]
        segment = row.get("customer_segment", "standard")
        risk_band = row.get("risk_band", "medium_risk")
        preferred_ch = row.get("preferred_channel", "email")
        digital_adop = float(row.get("digital_adoption", row.get("digital_adoption_30d", 0.3)))
        dominant_group = row.get("dominant_mcc_group", "general")

        # Determine offer category from triggers (priority: SHAP trigger → dominant group → general)
        offer_category = "general"
        top_trigger = str(row.get("top_trigger_1", ""))
        trigger_dir = str(row.get("top_trigger_1_dir", ""))
        if top_trigger.startswith("mcc_") and trigger_dir == "low":
            for grp in mcc_group_map.values() if hasattr(mcc_group_map, "values") else []:
                if f"mcc_{grp}_" in top_trigger:
                    offer_category = grp
                    break
            if offer_category == "general":
                parts = top_trigger.replace("mcc_", "").split("_")
                if parts:
                    offer_category = parts[0]
        elif dominant_group and dominant_group not in ["unknown", "other", ""]:
            offer_category = dominant_group

        # Get offer value
        key = (segment, risk_band)
        offer_type, offer_value, offer_duration = OFFER_VALUE_TABLE.get(
            key, ("cashback", 0.05, 30)
        )

        # Check if escalated
        if row.get("action_1_escalated", False):
            if offer_type == "cashback":
                offer_value = min(0.15, offer_value + 0.05)
            elif offer_type == "statement_credit":
                offer_value += 5

        favorite_merchant = get_favorite_merchant(cid, offer_category)

        specific_action = _render_offer_action(
            offer_category, segment, risk_band,
            favorite_merchant, offer_duration, offer_type, offer_value, templates,
        )

        primary_ch, secondary_ch = _select_offer_channel(preferred_ch, digital_adop)
        send_hour, send_dow, first_send = _compute_send_schedule(
            primary_ch, preferred_ch, [1, 4, 10], run_date,
        )

        expiry_date = (run_date + timedelta(days=offer_duration)).strftime("%Y-%m-%d")

        n_times = FREQ_BY_RISK.get(risk_band, 1)
        frequency_window = 7 if risk_band == "high_risk" else 14

        # Build personalization vars
        perso_vars = {
            "offer_category_label": offer_category,
            "specific_action_label": specific_action,
            "offer_value": f"{int(offer_value * 100)}% cashback" if offer_type == "cashback" else str(offer_value),
            "offer_type": offer_type,
            "offer_expiry_date": expiry_date,
            "favorite_merchant": favorite_merchant,
            "n_times_needed": n_times,
            "offer_duration_days": offer_duration,
        }

        row_out = dict(row)
        row_out.update({
            "offer_category": offer_category,
            "offer_type": offer_type,
            "offer_value": offer_value,
            "offer_duration_days": offer_duration,
            "offer_expiry_date": expiry_date,
            "specific_action": specific_action,
            "primary_channel": primary_ch,
            "secondary_channel": secondary_ch,
            "send_hour_utc": send_hour,
            "send_day_of_week": send_dow,
            "first_scheduled_send": first_send,
            "frequency_touches": n_times,
            "frequency_window_days": frequency_window,
            "favorite_merchant_in_category": favorite_merchant,
            "personalization_vars": str(perso_vars),
            "suppression_flag": False,
        })
        rows.append(row_out)

    return pd.DataFrame(rows)
