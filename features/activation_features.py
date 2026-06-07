"""Feature engineering for the activation cohort (new cards, first 90 days)."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from features.base_features import (
    build_mcc_group_map,
    compute_rolling_txn_count,
    compute_rolling_spend,
    compute_channel_diversity,
    compute_mcc_diversity,
    compute_digital_adoption,
    detect_recurring_transactions,
    compute_mcc_group_features,
    compute_preferred_channel,
    compute_dominant_mcc_group,
)

ACTIVATION_FEATURE_COLS = [
    "days_since_card_issue",
    "total_transactions_30d", "total_transactions_60d",
    "total_spend_30d", "total_spend_60d",
    "first_transaction_day",
    "channel_diversity",
    "mcc_diversity",
    "has_recurring_txn",
    "avg_txn_amount",
    "digital_adoption",
    "txn_rate_acceleration",
]


def compute_activation_features(
    txn_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    run_date: datetime,
    config: dict,
) -> pd.DataFrame:
    """Compute all activation features for the new-card cohort."""
    acfg = config["activation"]
    window = acfg["new_card_window_days"]
    mcc_group_map = build_mcc_group_map(config["mcc_groups"])

    # Scope: cards issued within last 90 days
    cutoff = run_date - timedelta(days=window)
    cohort = customers_df[
        (customers_df["card_issue_date"] >= cutoff) &
        (customers_df["card_issue_date"] <= run_date)
    ].copy()
    cohort = cohort.set_index("customer_id")

    if len(cohort) == 0:
        return pd.DataFrame()

    cohort_txns = txn_df[txn_df["customer_id"].isin(cohort.index)].copy()

    # Reference date per customer: min(run_date, card_issue_date + 90d)
    ref_dates = cohort["card_issue_date"].apply(
        lambda d: min(run_date, d + timedelta(days=window))
    )
    # For feature windows, use card_issue_date as the start anchor
    issue_dates = cohort["card_issue_date"]

    # Days since card issue
    days_since_issue = (ref_dates - issue_dates).dt.days.rename("days_since_card_issue")

    # Post-issue transaction subset
    def _post_issue_txns(cid, issue_date):
        return cohort_txns[
            (cohort_txns["customer_id"] == cid) &
            (cohort_txns["transaction_date"] >= issue_date)
        ]

    # Compute rolling counts/spend relative to card_issue_date
    # Build per-customer windows manually for activation (anchor = issue_date, not run_date)
    txn_30 = _compute_from_issue(cohort_txns, issue_dates, 30, "total_transactions_30d", "count")
    txn_60 = _compute_from_issue(cohort_txns, issue_dates, 60, "total_transactions_60d", "count")
    spend_30 = _compute_from_issue(cohort_txns, issue_dates, 30, "total_spend_30d", "sum")
    spend_60 = _compute_from_issue(cohort_txns, issue_dates, 60, "total_spend_60d", "sum")

    # First transaction day (days from card issue to first transaction)
    first_txn_dates = cohort_txns[cohort_txns["transaction_type"] != "refund"].groupby(
        "customer_id"
    )["transaction_date"].min()
    first_txn_day = (
        (first_txn_dates - issue_dates)
        .dt.days
        .reindex(cohort.index)
    )
    first_txn_day = first_txn_day.fillna(999).clip(lower=0).rename("first_transaction_day")

    # Channel and MCC diversity (post-issue, up to ref_date)
    channel_div = _compute_diversity_from_issue(cohort_txns, issue_dates, ref_dates, "channel", "channel_diversity")
    mcc_div = _compute_diversity_from_issue(cohort_txns, issue_dates, ref_dates, "merchant_category_code", "mcc_diversity")

    # Has recurring transactions
    has_recurring = detect_recurring_transactions(cohort_txns).reindex(cohort.index, fill_value=False)

    # Average transaction amount
    avg_amount = cohort_txns[cohort_txns["transaction_type"] != "refund"].groupby(
        "customer_id"
    )["transaction_amount"].mean().reindex(cohort.index, fill_value=0).rename("avg_txn_amount")

    # Digital adoption (% mobile+web transactions post-issue)
    digital_adop = _compute_digital_adoption_from_issue(cohort_txns, issue_dates, ref_dates)

    # Transaction rate acceleration: second half of 30d vs first half
    txn_accel = _compute_txn_acceleration(cohort_txns, issue_dates, ref_dates)

    # MCC group features (post-issue, 60d window)
    mcc_ref_dates = pd.Series(
        {cid: issue_dates[cid] + timedelta(days=60) for cid in cohort.index},
        name="ref_date",
    )
    # Clip to run_date
    mcc_ref_dates = mcc_ref_dates.apply(lambda d: min(d, run_date))
    mcc_group_feats = compute_mcc_group_features(cohort_txns, mcc_ref_dates, 60, mcc_group_map)

    # Routing metadata (not model features)
    preferred_ch = _compute_preferred_channel_from_issue(cohort_txns, issue_dates, ref_dates)
    dominant_grp = _compute_dominant_mcc_group_from_issue(cohort_txns, issue_dates, ref_dates, mcc_group_map)

    # Assemble
    features = pd.DataFrame({
        "days_since_card_issue": days_since_issue,
        "total_transactions_30d": txn_30,
        "total_transactions_60d": txn_60,
        "total_spend_30d": spend_30,
        "total_spend_60d": spend_60,
        "first_transaction_day": first_txn_day,
        "channel_diversity": channel_div,
        "mcc_diversity": mcc_div,
        "has_recurring_txn": has_recurring.astype(int),
        "avg_txn_amount": avg_amount,
        "digital_adoption": digital_adop,
        "txn_rate_acceleration": txn_accel,
        # routing metadata
        "preferred_channel": preferred_ch,
        "dominant_mcc_group": dominant_grp,
        "customer_segment": cohort["customer_segment"],
        "card_issue_date": cohort["card_issue_date"],
    })

    features = pd.concat([features, mcc_group_feats], axis=1)

    # Target label: is_activated (only label customers past day 60, right-censoring guard)
    past_60 = days_since_issue >= 60
    activated = (txn_60 >= acfg["min_transaction_count"]) & (spend_60 >= acfg["min_spend_threshold"])
    features["is_activated"] = np.where(past_60, activated.astype(int), np.nan)

    return features.reset_index().rename(columns={"index": "customer_id", "customer_id": "customer_id"})


def _compute_from_issue(txn_df, issue_dates, window_days, col_name, agg):
    result = {}
    for cid, issue_date in issue_dates.items():
        end = issue_date + timedelta(days=window_days)
        mask = (
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] >= issue_date) &
            (txn_df["transaction_date"] <= end) &
            (txn_df["transaction_type"] != "refund")
        )
        sub = txn_df[mask]
        if agg == "count":
            result[cid] = len(sub)
        else:
            result[cid] = sub["net_amount"].clip(lower=0).sum()
    return pd.Series(result, name=col_name)


def _compute_diversity_from_issue(txn_df, issue_dates, ref_dates, col, out_name):
    result = {}
    for cid in issue_dates.index:
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] >= issue_dates[cid]) &
            (txn_df["transaction_date"] <= ref_dates[cid])
        ]
        result[cid] = sub[col].nunique()
    return pd.Series(result, name=out_name)


def _compute_digital_adoption_from_issue(txn_df, issue_dates, ref_dates):
    result = {}
    for cid in issue_dates.index:
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] >= issue_dates[cid]) &
            (txn_df["transaction_date"] <= ref_dates[cid]) &
            (txn_df["transaction_type"] != "refund")
        ]
        if len(sub) == 0:
            result[cid] = 0.0
        else:
            result[cid] = sub["channel"].isin(["mobile_app", "web"]).sum() / len(sub)
    return pd.Series(result, name="digital_adoption")


def _compute_txn_acceleration(txn_df, issue_dates, ref_dates):
    result = {}
    for cid in issue_dates.index:
        issue = issue_dates[cid]
        mid = issue + timedelta(days=15)
        end30 = issue + timedelta(days=30)
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] >= issue) &
            (txn_df["transaction_type"] != "refund")
        ]
        first_half = sub[sub["transaction_date"] < mid]
        second_half = sub[(sub["transaction_date"] >= mid) & (sub["transaction_date"] <= end30)]
        n1 = len(first_half)
        n2 = len(second_half)
        if n1 == 0:
            result[cid] = 1.0 if n2 > 0 else 0.0
        else:
            result[cid] = n2 / n1
    return pd.Series(result, name="txn_rate_acceleration")


def _compute_preferred_channel_from_issue(txn_df, issue_dates, ref_dates):
    result = {}
    for cid in issue_dates.index:
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] >= issue_dates[cid]) &
            (txn_df["transaction_date"] <= ref_dates[cid]) &
            (txn_df["transaction_type"] != "refund")
        ]
        if len(sub) == 0:
            result[cid] = "unknown"
        else:
            result[cid] = sub["channel"].mode().iloc[0]
    return pd.Series(result, name="preferred_channel")


def _compute_dominant_mcc_group_from_issue(txn_df, issue_dates, ref_dates, mcc_group_map):
    result = {}
    for cid in issue_dates.index:
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] >= issue_dates[cid]) &
            (txn_df["transaction_date"] <= ref_dates[cid]) &
            (txn_df["transaction_type"] != "refund")
        ].copy()
        if len(sub) == 0:
            result[cid] = "unknown"
        else:
            sub["mcc_group"] = sub["merchant_category_code"].map(mcc_group_map).fillna("other")
            result[cid] = sub["mcc_group"].mode().iloc[0]
    return pd.Series(result, name="dominant_mcc_group")
