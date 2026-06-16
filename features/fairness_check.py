"""Post-scoring fairness analysis using the 80% (four-fifths) rule."""
import pandas as pd
import numpy as np


def compute_disparity_report(
    scores_df: pd.DataFrame,
    group_col: str = "customer_segment",
    score_col: str = "ml_probability",
    threshold_col: str = "risk_band",
    adverse_band: str = "high_risk",
) -> dict:
    """
    Check for disparate impact across groups using the 80% rule.
    Adverse action rate = fraction of group flagged as high_risk.
    If any group's rate < 80% of the highest-rate group, flag for review.
    """
    if group_col not in scores_df.columns:
        return {"status": "skipped", "reason": f"Column {group_col} not found"}

    group_rates = (
        scores_df.groupby(group_col)[threshold_col]
        .apply(lambda x: (x == adverse_band).mean())
        .rename("adverse_action_rate")
    )
    max_rate = group_rates.max()
    if max_rate == 0:
        return {"status": "ok", "message": "No high-risk customers flagged"}

    disparity_ratios = (group_rates / max_rate).rename("disparity_ratio_vs_max")
    violations = disparity_ratios[disparity_ratios < 0.80]

    report = {
        "status": "violation" if len(violations) > 0 else "ok",
        "group_adverse_action_rates": group_rates.to_dict(),
        "disparity_ratios": disparity_ratios.to_dict(),
        "violations": violations.to_dict(),
        "rule": "80% (four-fifths) rule: any group below 80% of the highest adverse action rate",
    }
    if len(violations) > 0:
        print(f"[FAIRNESS ALERT] Disparity violations detected: {violations.to_dict()}")
    return report
