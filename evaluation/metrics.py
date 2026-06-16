"""Model evaluation metrics: AUC, lift, activation/retention rates."""
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score, f1_score


def compute_model_metrics(y_true: pd.Series, y_prob: pd.Series, threshold: float = 0.5) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    metrics = {
        "auc_roc": float(roc_auc_score(y_true, y_prob)) if y_true.nunique() > 1 else 0.0,
        "auc_pr": float(average_precision_score(y_true, y_prob)) if y_true.nunique() > 1 else 0.0,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "threshold": threshold,
        "n_positive": int(y_true.sum()),
        "n_total": int(len(y_true)),
        "positive_rate": float(y_true.mean()),
    }
    # Lift at top deciles
    for pct in [10, 20, 30]:
        metrics[f"lift_at_top_{pct}pct"] = compute_lift_at_k(y_true, y_prob, pct / 100)
    return metrics


def compute_lift_at_k(y_true: pd.Series, y_prob: pd.Series, k: float) -> float:
    """Lift of top-k% scored customers vs. random baseline."""
    n = len(y_true)
    top_k_n = max(1, int(n * k))
    sorted_idx = y_prob.argsort()[::-1]
    top_k_true = y_true.iloc[sorted_idx[:top_k_n]] if isinstance(y_true, pd.Series) else y_true[sorted_idx[:top_k_n]]
    baseline_rate = float(y_true.mean())
    if baseline_rate == 0:
        return 0.0
    top_k_rate = float(top_k_true.mean())
    return round(top_k_rate / baseline_rate, 3)


def compute_activation_rate(
    customers_df: pd.DataFrame,
    txn_df: pd.DataFrame,
    cohort_date_start,
    cohort_date_end,
    window_days: int = 90,
    min_txn_count: int = 3,
    min_spend: float = 100.0,
) -> dict:
    cohort = customers_df[
        (customers_df["card_issue_date"] >= cohort_date_start) &
        (customers_df["card_issue_date"] <= cohort_date_end)
    ]
    if len(cohort) == 0:
        return {"activation_rate": 0.0, "n_cohort": 0, "n_activated": 0}

    activated = set()
    for _, cust in cohort.iterrows():
        issue = cust["card_issue_date"]
        end = issue + pd.Timedelta(days=window_days)
        cust_txns = txn_df[
            (txn_df["customer_id"] == cust["customer_id"]) &
            (txn_df["transaction_date"] >= issue) &
            (txn_df["transaction_date"] <= end) &
            (txn_df["transaction_type"].isin(["purchase", "recurring"]))
        ]
        if len(cust_txns) >= min_txn_count and cust_txns["net_amount"].clip(lower=0).sum() >= min_spend:
            activated.add(cust["customer_id"])

    return {
        "activation_rate": round(len(activated) / len(cohort), 4),
        "n_cohort": len(cohort),
        "n_activated": len(activated),
        "cohort_date_start": str(cohort_date_start),
        "cohort_date_end": str(cohort_date_end),
    }


def compute_retention_rate(
    customers_df: pd.DataFrame,
    txn_df: pd.DataFrame,
    base_start,
    base_end,
    followup_start,
    followup_end,
    min_txn: int = 1,
) -> dict:
    """% of customers active in base period still active in follow-up period."""
    base_active = set(
        txn_df[
            (txn_df["transaction_date"] >= base_start) &
            (txn_df["transaction_date"] <= base_end) &
            (txn_df["transaction_type"] != "refund")
        ]["customer_id"].unique()
    )
    if len(base_active) == 0:
        return {"retention_rate": 0.0, "n_base_active": 0, "n_retained": 0}

    follow_active = set(
        txn_df[
            (txn_df["transaction_date"] >= followup_start) &
            (txn_df["transaction_date"] <= followup_end) &
            (txn_df["transaction_type"] != "refund")
        ]["customer_id"].unique()
    )
    retained = base_active & follow_active
    return {
        "retention_rate": round(len(retained) / len(base_active), 4),
        "n_base_active": len(base_active),
        "n_retained": len(retained),
        "base_period": f"{base_start} to {base_end}",
        "followup_period": f"{followup_start} to {followup_end}",
    }


def compute_expected_lift(
    scores_df: pd.DataFrame,
    action_catalog: dict,
    baseline_rate: float,
    avg_annual_revenue: float = 1200.0,
) -> list:
    """Rank actions by ROI using expected lift from config."""
    results = []
    for action_type, params in action_catalog.items():
        response_rate = params.get("baseline_response_rate", 0.1)
        incremental_lift = params.get("incremental_lift", 0.0)
        cost_per_customer = params.get("cost_per_customer", 1.0)
        n_customers = len(scores_df)

        incremental_customers = n_customers * incremental_lift
        total_cost = n_customers * cost_per_customer
        incremental_revenue = incremental_customers * avg_annual_revenue
        roi = (incremental_revenue - total_cost) / max(total_cost, 1)

        results.append({
            "action_type": action_type,
            "est_response_rate": response_rate,
            "incremental_lift": incremental_lift,
            "cost_per_customer": cost_per_customer,
            "n_customers": n_customers,
            "incremental_customers": round(incremental_customers),
            "total_cost": round(total_cost, 2),
            "incremental_revenue": round(incremental_revenue, 2),
            "roi": round(roi, 3),
        })

    return sorted(results, key=lambda x: x["roi"], reverse=True)
