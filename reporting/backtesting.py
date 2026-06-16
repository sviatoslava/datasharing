"""Retrospective backtesting on completed cohorts."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def run_backtesting(
    txn_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    activation_model,  # has predict_proba(features_df) method
    config: dict,
    run_date: datetime,
    n_cohorts: int = 3,
) -> dict:
    """
    For each of the last n_cohorts monthly cohorts (cards issued 4, 5, ..., n+3 months ago),
    re-compute activation features AS OF card_issue_date + 90d,
    score with the trained model, compare to actual activation.

    Returns dict with:
      cohorts: list of per-cohort results
      model_stable: bool (True if max AUC variance across cohorts < 0.05)
      avg_auc: float
    """
    # Return early if the model has not been trained yet
    if getattr(activation_model, "model", None) is None:
        return {"cohorts": [], "model_stable": False, "avg_auc": None}

    min_txn_count = config["activation"]["min_transaction_count"]
    min_spend = config["activation"]["min_spend_threshold"]

    # Determine which column to use for spend
    spend_col = "net_amount" if "net_amount" in txn_df.columns else "transaction_amount"

    # Ensure datetime columns are proper datetimes
    customers_df = customers_df.copy()
    customers_df["card_issue_date"] = pd.to_datetime(customers_df["card_issue_date"])

    txn_df = txn_df.copy()
    txn_df["transaction_date"] = pd.to_datetime(txn_df["transaction_date"])

    cohort_results = []
    aucs = []

    for month_offset in range(1, n_cohorts + 1):
        cohort_start = run_date - relativedelta(months=month_offset + 3)
        cohort_end = run_date - relativedelta(months=month_offset + 2)
        cohort_label = cohort_start.strftime("%b-%Y")

        try:
            # Select customers whose card was issued in this cohort window
            cohort_customers = customers_df[
                (customers_df["card_issue_date"] >= cohort_start)
                & (customers_df["card_issue_date"] < cohort_end)
            ].copy()

            n_customers = len(cohort_customers)

            if n_customers == 0:
                cohort_results.append({
                    "cohort_label": cohort_label,
                    "cohort_start": cohort_start.strftime("%Y-%m-%d"),
                    "cohort_end": cohort_end.strftime("%Y-%m-%d"),
                    "n_customers": 0,
                    "n_predicted_nonactivating": 0,
                    "n_actual_nonactivating": 0,
                    "miss_rate": None,
                    "auc": None,
                    "lift_at_10pct": None,
                })
                continue

            # Compute features per customer as of card_issue_date + 90 days
            feature_rows = []
            for _, cust in cohort_customers.iterrows():
                cid = cust["customer_id"]
                issue_date = cust["card_issue_date"]
                window_end = issue_date + timedelta(days=60)
                scoring_date = issue_date + timedelta(days=90)

                # Filter transactions for this customer within [issue_date, issue_date+60d]
                cust_txns = txn_df[
                    (txn_df["customer_id"] == cid)
                    & (txn_df["transaction_date"] >= issue_date)
                    & (txn_df["transaction_date"] <= window_end)
                ]

                total_transactions_60d = len(cust_txns)
                total_spend_60d = cust_txns[spend_col].sum() if len(cust_txns) > 0 else 0.0

                if len(cust_txns) > 0:
                    first_txn_date = cust_txns["transaction_date"].min()
                    first_transaction_day = (first_txn_date - issue_date).days
                else:
                    first_transaction_day = 999

                if "transaction_type" in cust_txns.columns:
                    has_recurring_txn = int(
                        (cust_txns["transaction_type"] == "recurring").any()
                    )
                else:
                    has_recurring_txn = 0

                feature_rows.append({
                    "customer_id": cid,
                    "days_since_card_issue": 90,
                    "total_transactions_60d": total_transactions_60d,
                    "total_spend_60d": total_spend_60d,
                    "first_transaction_day": first_transaction_day,
                    "has_recurring_txn": has_recurring_txn,
                    "channel_diversity": 0,
                    "mcc_diversity": 0,
                    "digital_adoption": 0,
                })

            features_df = pd.DataFrame(feature_rows)

            # Compute actual activation labels
            features_df["is_activated"] = (
                (features_df["total_transactions_60d"] >= min_txn_count)
                & (features_df["total_spend_60d"] >= min_spend)
            ).astype(int)

            # Align features to model's expected columns, filling missing with 0
            model_feature_cols = activation_model.feature_cols
            for col in model_feature_cols:
                if col not in features_df.columns:
                    features_df[col] = 0
            X = features_df[model_feature_cols].fillna(0)

            # Score with the model
            scores = activation_model.predict_proba(X)
            features_df["score"] = scores

            actual_labels = features_df["is_activated"].values
            n_actual_nonactivating = int((actual_labels == 0).sum())

            # Predicted non-activating: score < 0.5
            n_predicted_nonactivating = int((features_df["score"] < 0.5).sum())

            miss_rate = abs(n_predicted_nonactivating - n_actual_nonactivating) / max(
                n_actual_nonactivating, 1
            )

            # Compute AUC-ROC
            auc = None
            lift_at_10pct = None

            unique_classes = np.unique(actual_labels)
            if n_customers >= 10 and len(unique_classes) > 1:
                from sklearn.metrics import roc_auc_score

                auc = float(roc_auc_score(actual_labels, features_df["score"].values))
                aucs.append(auc)

                # Lift @ 10%
                n_top = max(1, int(np.ceil(n_customers * 0.10)))
                top_customers = features_df.nlargest(n_top, "score")
                top_activation_rate = top_customers["is_activated"].mean()
                overall_activation_rate = features_df["is_activated"].mean()
                if overall_activation_rate > 0:
                    lift_at_10pct = float(top_activation_rate / overall_activation_rate)
                else:
                    lift_at_10pct = None

            cohort_results.append({
                "cohort_label": cohort_label,
                "cohort_start": cohort_start.strftime("%Y-%m-%d"),
                "cohort_end": cohort_end.strftime("%Y-%m-%d"),
                "n_customers": n_customers,
                "n_predicted_nonactivating": n_predicted_nonactivating,
                "n_actual_nonactivating": n_actual_nonactivating,
                "miss_rate": float(miss_rate),
                "auc": auc,
                "lift_at_10pct": lift_at_10pct,
            })

        except Exception:
            cohort_results.append({
                "cohort_label": cohort_label,
                "cohort_start": cohort_start.strftime("%Y-%m-%d"),
                "cohort_end": cohort_end.strftime("%Y-%m-%d"),
                "n_customers": 0,
                "n_predicted_nonactivating": 0,
                "n_actual_nonactivating": 0,
                "miss_rate": None,
                "auc": None,
                "lift_at_10pct": None,
            })

    # Determine model stability
    if len(aucs) >= 2:
        model_stable = (max(aucs) - min(aucs)) < 0.05
    else:
        model_stable = False

    avg_auc = float(np.mean(aucs)) if aucs else None

    return {
        "cohorts": cohort_results,
        "model_stable": model_stable,
        "avg_auc": avg_auc,
    }
