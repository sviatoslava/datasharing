"""Feature engineering for the retention cohort (ever-active cards)."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from features.base_features import (
    build_mcc_group_map,
    compute_days_since_last_txn,
    detect_recurring_transactions,
    compute_mcc_group_features,
)

RETENTION_FEATURE_COLS = [
    "txn_count_30d", "txn_count_60d", "txn_count_90d",
    "spend_30d", "spend_60d", "spend_90d",
    "days_since_last_txn",
    "txn_velocity_change",
    "spend_velocity_change",
    "channel_shift",
    "avg_txn_amount_trend",
    "monthly_active_months",
    "has_recurring_txn",
    "digital_adoption_30d",
    "mcc_diversity_90d",
    "channel_diversity_90d",
]


def compute_retention_features(
    txn_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    run_date: datetime,
    config: dict,
    activation_customer_ids: set = None,
) -> pd.DataFrame:
    """Compute all retention features for the ever-active cohort."""
    rcfg = config["retention"]
    mcc_group_map = build_mcc_group_map(config["mcc_groups"])

    # Scope: customers NOT in activation cohort, with >= 3 lifetime qualifying txns
    activation_ids = activation_customer_ids or set()
    eligible_customers = customers_df[~customers_df["customer_id"].isin(activation_ids)].copy()

    # Compute lifetime qualifying transaction count per customer
    qualifying_txns = txn_df[
        (txn_df["transaction_type"].isin(["purchase", "recurring"])) &
        (txn_df["transaction_amount"] >= config["activation"]["min_transaction_amount"])
    ]
    lifetime_counts = qualifying_txns.groupby("customer_id")["transaction_id"].count()
    ever_active_ids = set(lifetime_counts[lifetime_counts >= 3].index)
    eligible_customers = eligible_customers[eligible_customers["customer_id"].isin(ever_active_ids)].copy()

    if len(eligible_customers) == 0:
        return pd.DataFrame()

    eligible_customers = eligible_customers.set_index("customer_id")
    cohort_txns = txn_df[txn_df["customer_id"].isin(eligible_customers.index)].copy()

    ref = run_date
    ref_series = pd.Series(ref, index=eligible_customers.index)

    # Rolling counts and spend for multiple windows
    results = {}
    for window in [30, 60, 90]:
        results[f"txn_count_{window}d"] = _rolling_count(cohort_txns, eligible_customers.index, ref, window)
        results[f"spend_{window}d"] = _rolling_spend(cohort_txns, eligible_customers.index, ref, window)

    # Days since last transaction
    last_txn = cohort_txns[cohort_txns["transaction_type"] != "refund"].groupby(
        "customer_id"
    )["transaction_date"].max()
    days_since = (ref - last_txn).dt.days.reindex(eligible_customers.index, fill_value=999)
    days_since.name = "days_since_last_txn"
    results["days_since_last_txn"] = days_since

    # Velocity features: current 30d vs prior 30d
    prior_txn_30d = _rolling_count(cohort_txns, eligible_customers.index, ref - timedelta(days=30), 30)
    prior_spend_30d = _rolling_spend(cohort_txns, eligible_customers.index, ref - timedelta(days=30), 30)

    velocity_txn = ((results["txn_count_30d"] - prior_txn_30d) / prior_txn_30d.clip(lower=1)).clip(-1, 5)
    velocity_spend = ((results["spend_30d"] - prior_spend_30d) / prior_spend_30d.clip(lower=1)).clip(-1, 5)
    results["txn_velocity_change"] = velocity_txn.rename("txn_velocity_change")
    results["spend_velocity_change"] = velocity_spend.rename("spend_velocity_change")

    # Channel shift: digital adoption change (current 30d vs prior 30d)
    digital_now = _digital_adoption(cohort_txns, eligible_customers.index, ref, 30)
    digital_prior = _digital_adoption(cohort_txns, eligible_customers.index, ref - timedelta(days=30), 30)
    results["channel_shift"] = (digital_now - digital_prior).rename("channel_shift")
    results["digital_adoption_30d"] = digital_now.rename("digital_adoption_30d")

    # Average transaction amount trend
    avg_now = _avg_amount(cohort_txns, eligible_customers.index, ref, 30)
    avg_prior = _avg_amount(cohort_txns, eligible_customers.index, ref - timedelta(days=30), 30)
    results["avg_txn_amount_trend"] = (avg_now - avg_prior).rename("avg_txn_amount_trend")

    # Monthly active months in last 6 months
    results["monthly_active_months"] = _monthly_active_months(cohort_txns, eligible_customers.index, ref, 6)

    # Seasonal customer flag (high variance in monthly txn counts)
    results["is_seasonal_customer"] = _is_seasonal(cohort_txns, eligible_customers.index, ref)

    # Has recurring transactions
    has_rec = detect_recurring_transactions(cohort_txns).reindex(eligible_customers.index, fill_value=False)
    results["has_recurring_txn"] = has_rec.astype(int)

    # Diversity features
    results["mcc_diversity_90d"] = _diversity(cohort_txns, eligible_customers.index, ref, 90, "merchant_category_code")
    results["channel_diversity_90d"] = _diversity(cohort_txns, eligible_customers.index, ref, 90, "channel")

    # MCC group features (30d and velocity)
    mcc_30 = _mcc_group_features(cohort_txns, eligible_customers.index, ref, 30, mcc_group_map)
    mcc_prior_30 = _mcc_group_features(cohort_txns, eligible_customers.index, ref - timedelta(days=30), 30, mcc_group_map)

    mcc_velocity = {}
    for col in mcc_30.columns:
        if col.endswith("_txn_cnt_30d"):
            group = col.replace("_txn_cnt_30d", "")
            prior_col = col
            vel_col = col.replace("_txn_cnt_30d", "_velocity_30d")
            vel = ((mcc_30[col] - mcc_prior_30[col]) / mcc_prior_30[col].clip(lower=1)).clip(-1, 5)
            mcc_velocity[vel_col] = vel

    # Dominant MCC group shift
    dom_now = _dominant_mcc_group(cohort_txns, eligible_customers.index, ref, 30, mcc_group_map)
    dom_prior = _dominant_mcc_group(cohort_txns, eligible_customers.index, ref - timedelta(days=30), 30, mcc_group_map)
    dominant_group_shift = (dom_now != dom_prior).astype(int).rename("dominant_mcc_group_shift")

    # Routing metadata (not model features)
    preferred_ch = _preferred_channel(cohort_txns, eligible_customers.index, ref, 90)
    dominant_grp = dom_now.rename("dominant_mcc_group")

    features = pd.DataFrame(results)
    features = pd.concat([features, mcc_30, pd.DataFrame(mcc_velocity), dominant_group_shift], axis=1)
    features["preferred_channel"] = preferred_ch
    features["dominant_mcc_group"] = dominant_grp
    features["customer_segment"] = eligible_customers["customer_segment"]
    features["lifetime_txn_count"] = lifetime_counts.reindex(eligible_customers.index, fill_value=0)

    # Target: is_churned (90d no qualifying txn, had >= min_prior_active_months active)
    min_active_months = rcfg["min_prior_active_months"]
    churn_days = rcfg["churn_label_days"]
    churned = (
        (days_since >= churn_days) &
        (features["monthly_active_months"] >= min_active_months) &
        (~features["is_seasonal_customer"].astype(bool))
    )
    features["is_churned"] = churned.astype(int)

    return features.reset_index().rename(columns={"index": "customer_id"})


def _rolling_count(txn_df, customer_ids, ref_date, window_days):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ]
    counts = sub.groupby("customer_id")["transaction_id"].count()
    return counts.reindex(customer_ids, fill_value=0).rename(f"txn_count_{window_days}d")


def _rolling_spend(txn_df, customer_ids, ref_date, window_days):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ]
    spend = sub.groupby("customer_id")["net_amount"].sum()
    return spend.reindex(customer_ids, fill_value=0).rename(f"spend_{window_days}d")


def _digital_adoption(txn_df, customer_ids, ref_date, window_days):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ].copy()
    if len(sub) == 0:
        return pd.Series(0.0, index=customer_ids)
    sub["is_digital"] = sub["channel"].isin(["mobile_app", "web"])
    rate = sub.groupby("customer_id").apply(lambda x: x["is_digital"].mean())
    return rate.reindex(customer_ids, fill_value=0.0)


def _avg_amount(txn_df, customer_ids, ref_date, window_days):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ]
    avg = sub.groupby("customer_id")["transaction_amount"].mean()
    return avg.reindex(customer_ids, fill_value=0.0)


def _monthly_active_months(txn_df, customer_ids, ref_date, n_months):
    result = {}
    for cid in customer_ids:
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] > ref_date - timedelta(days=n_months * 30)) &
            (txn_df["transaction_date"] <= ref_date) &
            (txn_df["transaction_type"] != "refund")
        ]
        if len(sub) == 0:
            result[cid] = 0
        else:
            result[cid] = sub["transaction_date"].dt.to_period("M").nunique()
    return pd.Series(result, name="monthly_active_months")


def _is_seasonal(txn_df, customer_ids, ref_date):
    result = {}
    for cid in customer_ids:
        sub = txn_df[
            (txn_df["customer_id"] == cid) &
            (txn_df["transaction_date"] > ref_date - timedelta(days=365)) &
            (txn_df["transaction_date"] <= ref_date) &
            (txn_df["transaction_type"] != "refund")
        ]
        if len(sub) < 3:
            result[cid] = False
        else:
            monthly = sub.groupby(sub["transaction_date"].dt.to_period("M"))["transaction_id"].count()
            result[cid] = bool(monthly.std() > monthly.mean() * 0.8 and monthly.sum() < 6)
    return pd.Series(result, name="is_seasonal_customer")


def _diversity(txn_df, customer_ids, ref_date, window_days, col):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ]
    div = sub.groupby("customer_id")[col].nunique()
    return div.reindex(customer_ids, fill_value=0).rename(f"{col}_diversity_{window_days}d")


def _mcc_group_features(txn_df, customer_ids, ref_date, window_days, mcc_group_map):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ].copy()
    sub["mcc_group"] = sub["merchant_category_code"].map(mcc_group_map).fillna("other")
    groups = list(set(mcc_group_map.values()))
    frames = []
    for group in groups:
        g_sub = sub[sub["mcc_group"] == group]
        cnt = g_sub.groupby("customer_id")["transaction_id"].count().reindex(customer_ids, fill_value=0)
        spend = g_sub.groupby("customer_id")["net_amount"].sum().reindex(customer_ids, fill_value=0)
        frames.append(cnt.rename(f"mcc_{group}_txn_cnt_{window_days}d"))
        frames.append(spend.rename(f"mcc_{group}_spend_{window_days}d"))
    return pd.concat(frames, axis=1)


def _preferred_channel(txn_df, customer_ids, ref_date, window_days):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ]
    if len(sub) == 0:
        return pd.Series("unknown", index=customer_ids, name="preferred_channel")
    pref = sub.groupby("customer_id")["channel"].agg(lambda x: x.mode().iloc[0] if len(x) else "unknown")
    return pref.reindex(customer_ids, fill_value="unknown").rename("preferred_channel")


def _dominant_mcc_group(txn_df, customer_ids, ref_date, window_days, mcc_group_map):
    cutoff = ref_date - timedelta(days=window_days)
    sub = txn_df[
        (txn_df["transaction_date"] >= cutoff) &
        (txn_df["transaction_date"] <= ref_date) &
        (txn_df["transaction_type"] != "refund")
    ].copy()
    sub["mcc_group"] = sub["merchant_category_code"].map(mcc_group_map).fillna("other")
    dom = sub.groupby("customer_id")["mcc_group"].agg(lambda x: x.mode().iloc[0] if len(x) else "unknown")
    return dom.reindex(customer_ids, fill_value="unknown").rename("dominant_mcc_group")
