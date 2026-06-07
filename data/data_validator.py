"""Transaction data quality validation and cleaning."""
import pandas as pd
import numpy as np
from datetime import datetime


def validate_transactions(
    txn_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    config: dict,
    run_date: datetime = None,
) -> tuple:
    """Clean and validate transaction data. Returns (clean_df, quality_report)."""
    acfg = config["activation"]
    run_date = run_date or datetime.now()
    report = {}

    original_count = len(txn_df)
    report["original_count"] = original_count

    # 1. Remove duplicate transaction IDs
    before = len(txn_df)
    txn_df = txn_df.drop_duplicates(subset=["transaction_id"])
    report["n_duplicates_removed"] = before - len(txn_df)

    # 2. Remove future-dated transactions
    before = len(txn_df)
    txn_df = txn_df[txn_df["transaction_date"] <= run_date]
    report["n_future_removed"] = before - len(txn_df)

    # 3. Remove orphan transactions (customer_id not in customers table)
    valid_customers = set(customers_df["customer_id"].unique())
    before = len(txn_df)
    txn_df = txn_df[txn_df["customer_id"].isin(valid_customers)]
    report["n_orphan_removed"] = before - len(txn_df)

    # 4. Net refunds against purchases
    # Match refunds to original purchase by (merchant_name, amount, within 7d)
    purchases = txn_df[txn_df["transaction_type"] == "purchase"].copy()
    refunds = txn_df[txn_df["transaction_type"] == "refund"].copy()

    if len(refunds) > 0:
        # Simple approach: mark refunds as netted, reduce spend accordingly
        # Store netted amounts in a separate column for feature computation
        txn_df["is_refund"] = txn_df["transaction_type"] == "refund"
        txn_df["net_amount"] = txn_df.apply(
            lambda r: -r["transaction_amount"] if r["transaction_type"] == "refund" else r["transaction_amount"],
            axis=1,
        )
        report["n_refunds"] = len(refunds)
    else:
        txn_df["is_refund"] = False
        txn_df["net_amount"] = txn_df["transaction_amount"]
        report["n_refunds"] = 0

    # 5. Filter excluded transaction types
    excluded = acfg.get("exclude_transaction_types", [])
    before = len(txn_df)
    txn_df_qualifying = txn_df[~txn_df["transaction_type"].isin(excluded)].copy()
    report["n_excluded_types"] = before - len(txn_df_qualifying)

    # 6. Filter below-minimum transaction amounts (authorization tests)
    min_amount = acfg.get("min_transaction_amount", 1.00)
    before = len(txn_df_qualifying)
    txn_df_qualifying = txn_df_qualifying[txn_df_qualifying["transaction_amount"] >= min_amount]
    report["n_below_min_amount"] = before - len(txn_df_qualifying)

    report["clean_count"] = len(txn_df_qualifying)
    report["retention_rate_pct"] = round(100 * report["clean_count"] / max(1, original_count), 2)

    return txn_df_qualifying, report
