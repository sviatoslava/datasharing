"""Persist intermediate pipeline step outputs to disk."""
import json
import os
from datetime import datetime
import pandas as pd
import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    """Convert numpy scalar types to Python native types for JSON serialization."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        return super().default(obj)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _outputs_dir(output_dir: str) -> str:
    _ensure_dir(output_dir)
    return output_dir


def save_data_quality_report(quality_report: dict, output_dir: str, date_str: str) -> str:
    """Write outputs/step2_data_quality_{date}.json"""
    out = _outputs_dir(output_dir)
    report = dict(quality_report)
    report["timestamp"] = datetime.utcnow().isoformat()
    report["run_date"] = date_str
    path = os.path.join(out, f"step2_data_quality_{date_str}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, cls=_NumpyEncoder)
    return path


def save_cohort_summary(
    activation_ids: set,
    customers_df: pd.DataFrame,
    run_date_dt: datetime,
    config: dict,
    output_dir: str,
    date_str: str,
) -> str:
    """Write outputs/step3_cohort_summary_{date}.json"""
    out = _outputs_dir(output_dir)

    activation_cohort = customers_df[customers_df["customer_id"].isin(activation_ids)]
    activation_cohort_size = len(activation_ids)
    total_customers = len(customers_df)
    retention_cohort_size = total_customers - activation_cohort_size

    # Segment breakdown
    segment_breakdown = {}
    for segment, group in customers_df.groupby("customer_segment"):
        act_n = int(group["customer_id"].isin(activation_ids).sum())
        total_n = int(len(group))
        ret_n = total_n - act_n
        segment_breakdown[str(segment)] = {
            "activation_n": act_n,
            "retention_n": ret_n,
            "total_n": total_n,
        }

    # Card issue date range for activation cohort
    if len(activation_cohort) > 0 and "card_issue_date" in activation_cohort.columns:
        issue_dates = pd.to_datetime(activation_cohort["card_issue_date"])
        card_issue_date_range = {
            "min": issue_dates.min().isoformat() if not pd.isna(issue_dates.min()) else None,
            "max": issue_dates.max().isoformat() if not pd.isna(issue_dates.max()) else None,
        }
        days_since = (run_date_dt - issue_dates).dt.days.dropna()
        median_days = float(days_since.median()) if len(days_since) > 0 else None
    else:
        card_issue_date_range = {"min": None, "max": None}
        median_days = None

    summary = {
        "run_date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "activation_cohort_size": int(activation_cohort_size),
        "retention_cohort_size": int(retention_cohort_size),
        "total_customers": int(total_customers),
        "new_card_window_days": config["activation"]["new_card_window_days"],
        "segment_breakdown": segment_breakdown,
        "card_issue_date_range": card_issue_date_range,
        "median_days_since_issue": median_days,
    }

    path = os.path.join(out, f"step3_cohort_summary_{date_str}.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, cls=_NumpyEncoder)
    return path


def save_features(
    activation_features: pd.DataFrame,
    retention_features: pd.DataFrame,
    output_dir: str,
    date_str: str,
) -> dict:
    """Write parquets and feature summary JSON"""
    out = _outputs_dir(output_dir)

    act_path = os.path.join(out, f"step4_activation_features_{date_str}.parquet")
    ret_path = os.path.join(out, f"step4_retention_features_{date_str}.parquet")
    summary_path = os.path.join(out, f"step4_feature_summary_{date_str}.json")

    activation_features.to_parquet(act_path, index=False)
    retention_features.to_parquet(ret_path, index=False)

    def _null_rates(df: pd.DataFrame) -> dict:
        if len(df) == 0:
            return {col: 0.0 for col in df.columns}
        return {col: float(df[col].isna().sum() / len(df)) for col in df.columns}

    def _activation_rate(df: pd.DataFrame) -> float | None:
        if "is_activated" not in df.columns or len(df) == 0:
            return None
        valid = df["is_activated"].dropna()
        return float(valid.mean()) if len(valid) > 0 else None

    def _churn_rate(df: pd.DataFrame) -> float | None:
        if "is_churned" not in df.columns or len(df) == 0:
            return None
        valid = df["is_churned"].dropna()
        return float(valid.mean()) if len(valid) > 0 else None

    act_n_features = len([c for c in activation_features.columns if c != "customer_id"])
    ret_n_features = len([c for c in retention_features.columns if c != "customer_id"])

    summary = {
        "activation": {
            "n_customers": int(len(activation_features)),
            "n_features": act_n_features,
            "columns": list(activation_features.columns),
            "null_rates": _null_rates(activation_features),
            "activation_rate": _activation_rate(activation_features),
        },
        "retention": {
            "n_customers": int(len(retention_features)),
            "n_features": ret_n_features,
            "columns": list(retention_features.columns),
            "null_rates": _null_rates(retention_features),
            "churn_rate": _churn_rate(retention_features),
        },
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, cls=_NumpyEncoder)

    return {
        "activation_features": act_path,
        "retention_features": ret_path,
        "feature_summary": summary_path,
    }


def save_scores_and_shap(
    act_scores_df: pd.DataFrame,
    ret_scores_df: pd.DataFrame,
    act_shap_df: pd.DataFrame,
    ret_shap_df: pd.DataFrame,
    output_dir: str,
    date_str: str,
) -> dict:
    """Write score parquets and merged SHAP parquet"""
    out = _outputs_dir(output_dir)
    paths = {}

    act_scores_path = os.path.join(out, f"step6_activation_scores_{date_str}.parquet")
    ret_scores_path = os.path.join(out, f"step6_retention_scores_{date_str}.parquet")
    shap_path = os.path.join(out, f"step6_shap_explanations_{date_str}.parquet")

    if len(act_scores_df) > 0:
        act_scores_df.to_parquet(act_scores_path, index=False)
        paths["activation_scores"] = act_scores_path

    if len(ret_scores_df) > 0:
        ret_scores_df.to_parquet(ret_scores_path, index=False)
        paths["retention_scores"] = ret_scores_path

    # Merge SHAP frames with model_type column
    shap_parts = []
    if len(act_shap_df) > 0:
        act_shap = act_shap_df.copy()
        act_shap["model_type"] = "activation"
        shap_parts.append(act_shap)
    if len(ret_shap_df) > 0:
        ret_shap = ret_shap_df.copy()
        ret_shap["model_type"] = "retention"
        shap_parts.append(ret_shap)

    if shap_parts:
        merged_shap = pd.concat(shap_parts, ignore_index=True)
    else:
        merged_shap = pd.DataFrame()

    merged_shap.to_parquet(shap_path, index=False)
    paths["shap_explanations"] = shap_path

    return paths


def save_fairness_report(fairness_report: dict, output_dir: str, date_str: str) -> str:
    """Write outputs/step6b_fairness_report_{date}.json"""
    out = _outputs_dir(output_dir)
    report = dict(fairness_report)
    report["timestamp"] = datetime.utcnow().isoformat()
    path = os.path.join(out, f"step6b_fairness_report_{date_str}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, cls=_NumpyEncoder)
    return path
