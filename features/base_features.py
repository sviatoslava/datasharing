"""Shared vectorized rolling-window feature utilities."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


MCC_GROUP_MAP = {}  # populated from config by caller


def build_mcc_group_map(mcc_groups_config: dict) -> dict:
    mapping = {}
    for group, mccs in mcc_groups_config.items():
        for mcc in mccs:
            mapping[mcc] = group
    return mapping


def _window_mask(txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int) -> pd.DataFrame:
    """Returns a boolean mask: transactions within [ref_date - window_days, ref_date] per customer."""
    merged = txn_df.merge(
        ref_dates.rename("ref_date").reset_index(),
        on="customer_id",
        how="inner",
    )
    cutoff = merged["ref_date"] - pd.to_timedelta(window_days, unit="D")
    mask = (merged["transaction_date"] >= cutoff) & (merged["transaction_date"] <= merged["ref_date"])
    return merged[mask]


def compute_rolling_txn_count(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int
) -> pd.Series:
    windowed = _window_mask(txn_df, ref_dates, window_days)
    counts = windowed.groupby("customer_id")["transaction_id"].count()
    return counts.reindex(ref_dates.index, fill_value=0).rename(f"txn_count_{window_days}d")


def compute_rolling_spend(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int
) -> pd.Series:
    windowed = _window_mask(txn_df, ref_dates, window_days)
    spend = windowed.groupby("customer_id")["net_amount"].sum()
    return spend.reindex(ref_dates.index, fill_value=0).rename(f"spend_{window_days}d")


def compute_days_since_last_txn(txn_df: pd.DataFrame, ref_dates: pd.Series) -> pd.Series:
    last_txn = txn_df.groupby("customer_id")["transaction_date"].max()
    result = {}
    for cid, ref_date in ref_dates.items():
        if cid in last_txn.index:
            result[cid] = (ref_date - last_txn[cid]).days
        else:
            result[cid] = 999
    return pd.Series(result, name="days_since_last_txn")


def compute_channel_diversity(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int
) -> pd.Series:
    windowed = _window_mask(txn_df, ref_dates, window_days)
    diversity = windowed.groupby("customer_id")["channel"].nunique()
    return diversity.reindex(ref_dates.index, fill_value=0).rename(f"channel_diversity_{window_days}d")


def compute_mcc_diversity(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int
) -> pd.Series:
    windowed = _window_mask(txn_df, ref_dates, window_days)
    diversity = windowed.groupby("customer_id")["merchant_category_code"].nunique()
    return diversity.reindex(ref_dates.index, fill_value=0).rename(f"mcc_diversity_{window_days}d")


def compute_digital_adoption(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int
) -> pd.Series:
    windowed = _window_mask(txn_df, ref_dates, window_days)
    if len(windowed) == 0:
        return pd.Series(0.0, index=ref_dates.index, name=f"digital_adoption_{window_days}d")
    windowed = windowed.copy()
    windowed["is_digital"] = windowed["channel"].isin(["mobile_app", "web"])
    digital_rate = windowed.groupby("customer_id").apply(
        lambda x: x["is_digital"].sum() / max(1, len(x))
    )
    return digital_rate.reindex(ref_dates.index, fill_value=0).rename(f"digital_adoption_{window_days}d")


def detect_recurring_transactions(txn_df: pd.DataFrame) -> pd.Series:
    """Detect customers with recurring (fixed-merchant, fixed-amount) monthly patterns."""
    recurring = txn_df[txn_df["transaction_type"] == "recurring"]
    has_recurring = recurring.groupby("customer_id")["transaction_id"].count() >= 1
    return has_recurring.reindex(
        txn_df["customer_id"].unique(), fill_value=False
    ).rename("has_recurring_txn")


def compute_mcc_group_features(
    txn_df: pd.DataFrame,
    ref_dates: pd.Series,
    window_days: int,
    mcc_group_map: dict,
) -> pd.DataFrame:
    """Compute per-MCC-group transaction count and spend within window."""
    txn_with_group = txn_df.copy()
    txn_with_group["mcc_group"] = txn_with_group["merchant_category_code"].map(mcc_group_map)

    windowed = _window_mask(txn_with_group, ref_dates, window_days)
    if len(windowed) == 0:
        groups = list(set(mcc_group_map.values()))
        cols = {}
        for g in groups:
            cols[f"mcc_{g}_txn_cnt_{window_days}d"] = 0
            cols[f"mcc_{g}_spend_{window_days}d"] = 0.0
        return pd.DataFrame(cols, index=ref_dates.index)

    groups = list(set(mcc_group_map.values()))
    result_frames = []
    for group in groups:
        group_txns = windowed[windowed["mcc_group"] == group]
        cnt = group_txns.groupby("customer_id")["transaction_id"].count().reindex(ref_dates.index, fill_value=0)
        spend = group_txns.groupby("customer_id")["net_amount"].sum().reindex(ref_dates.index, fill_value=0)
        result_frames.append(cnt.rename(f"mcc_{group}_txn_cnt_{window_days}d"))
        result_frames.append(spend.rename(f"mcc_{group}_spend_{window_days}d"))

    return pd.concat(result_frames, axis=1)


def compute_preferred_channel(txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int) -> pd.Series:
    """Mode channel in recent window — routing metadata, not a model feature."""
    windowed = _window_mask(txn_df, ref_dates, window_days)
    if len(windowed) == 0:
        return pd.Series("unknown", index=ref_dates.index, name="preferred_channel")
    preferred = windowed.groupby("customer_id")["channel"].agg(
        lambda x: x.mode().iloc[0] if len(x) > 0 else "unknown"
    )
    return preferred.reindex(ref_dates.index, fill_value="unknown").rename("preferred_channel")


def compute_dominant_mcc_group(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int, mcc_group_map: dict
) -> pd.Series:
    """Mode MCC group in recent window — routing metadata, not a model feature."""
    txn_with_group = txn_df.copy()
    txn_with_group["mcc_group"] = txn_with_group["merchant_category_code"].map(mcc_group_map).fillna("other")
    windowed = _window_mask(txn_with_group, ref_dates, window_days)
    if len(windowed) == 0:
        return pd.Series("unknown", index=ref_dates.index, name="dominant_mcc_group")
    dominant = windowed.groupby("customer_id")["mcc_group"].agg(
        lambda x: x.mode().iloc[0] if len(x) > 0 else "unknown"
    )
    return dominant.reindex(ref_dates.index, fill_value="unknown").rename("dominant_mcc_group")


def compute_favorite_merchant_in_group(
    txn_df: pd.DataFrame, ref_dates: pd.Series, window_days: int,
    dominant_groups: pd.Series, mcc_group_map: dict,
) -> pd.Series:
    """Most frequent merchant in the customer's dominant MCC group."""
    txn_with_group = txn_df.copy()
    txn_with_group["mcc_group"] = txn_with_group["merchant_category_code"].map(mcc_group_map).fillna("other")
    windowed = _window_mask(txn_with_group, ref_dates, window_days)
    result = {}
    for cid in ref_dates.index:
        grp = dominant_groups.get(cid, "unknown")
        cust_txns = windowed[(windowed["customer_id"] == cid) & (windowed["mcc_group"] == grp)]
        if len(cust_txns) > 0:
            result[cid] = cust_txns["merchant_name"].mode().iloc[0]
        else:
            result[cid] = "unknown"
    return pd.Series(result, name="favorite_merchant_in_group")
