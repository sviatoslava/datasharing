"""Population Stability Index (PSI) monitoring for model features."""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime


def compute_psi(expected: pd.Series, actual: pd.Series, n_bins: int = 10) -> float:
    """Compute PSI between expected (training) and actual (scoring) distributions."""
    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())
    if min_val == max_val:
        return 0.0

    bins = np.linspace(min_val, max_val, n_bins + 1)
    exp_counts, _ = np.histogram(expected, bins=bins)
    act_counts, _ = np.histogram(actual, bins=bins)

    exp_pct = (exp_counts + 0.0001) / len(expected)
    act_pct = (act_counts + 0.0001) / len(actual)

    psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
    return float(psi)


def monitor_stability(
    scoring_features: pd.DataFrame,
    training_stats: dict,
    feature_cols: list,
    alert_threshold: float = 0.25,
) -> dict:
    """
    Compare scoring population feature distributions vs. training baseline.
    PSI < 0.10: no significant change
    PSI 0.10-0.25: moderate shift, monitor
    PSI > 0.25: significant shift, consider retraining
    """
    results = {}
    alerts = []
    for col in feature_cols:
        if col not in scoring_features.columns or col not in training_stats:
            continue
        train_mean = training_stats[col]["mean"]
        train_std = training_stats[col]["std"]
        if train_std == 0:
            continue
        # Generate approximate training distribution from stats
        n_ref = 1000
        train_approx = np.random.normal(train_mean, max(train_std, 0.01), n_ref)
        actual_vals = scoring_features[col].dropna().values
        if len(actual_vals) < 10:
            continue
        psi = compute_psi(pd.Series(train_approx), pd.Series(actual_vals))
        results[col] = {
            "psi": round(psi, 4),
            "status": "ok" if psi < 0.10 else ("monitor" if psi < alert_threshold else "alert"),
        }
        if psi >= alert_threshold:
            alerts.append(col)

    report = {
        "timestamp": datetime.now().isoformat(),
        "n_features_checked": len(results),
        "n_alerts": len(alerts),
        "alert_features": alerts,
        "retraining_recommended": len(alerts) > 0,
        "feature_psi": results,
    }
    if alerts:
        print(f"[STABILITY ALERT] PSI > {alert_threshold} for features: {alerts}")
    return report


def save_stability_report(report: dict, output_dir: str, run_date: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"stability_report_{run_date}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path
