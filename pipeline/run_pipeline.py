"""End-to-end pipeline orchestrator: data → features → models → scores → actions → outputs."""
import os
import sys
import json
import yaml
import click
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.generate_data import generate
from data.data_validator import validate_transactions
from features.activation_features import compute_activation_features
from features.retention_features import compute_retention_features
from features.fairness_check import compute_disparity_report
from features.base_features import build_mcc_group_map
from models.activation_model import ActivationModel
from models.retention_model import RetentionModel
from model_governance.stability_monitor import monitor_stability, save_stability_report
from actions.action_engine import assign_actions
from actions.offer_generator import generate_offers
from pipeline.campaign_builder import build_campaign_schedule
from pipeline.crm_export import export_crm_files
from pipeline.feedback_ingestion import run_feedback_ingestion
from evaluation.metrics import compute_model_metrics, compute_activation_rate, compute_retention_rate
from evaluation.campaign_evaluator import run_evaluation
from reporting.step_outputs import (
    save_data_quality_report, save_cohort_summary, save_features,
    save_scores_and_shap, save_fairness_report,
)
from reporting.business_report import generate_business_report
from reporting.backtesting import run_backtesting


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_data(config: dict, output_dir: str) -> tuple:
    raw_dir = config["data"]["raw_dir"]
    customers_path = os.path.join(raw_dir, "customers.parquet")
    txn_path = os.path.join(raw_dir, "transactions.parquet")
    customers_df = pd.read_parquet(customers_path)
    txn_df = pd.read_parquet(txn_path)
    customers_df["card_issue_date"] = pd.to_datetime(customers_df["card_issue_date"])
    txn_df["transaction_date"] = pd.to_datetime(txn_df["transaction_date"])
    return customers_df, txn_df


def find_latest_model(registry_dir: str, model_prefix: str) -> str | None:
    if not os.path.exists(registry_dir):
        return None
    files = [f for f in os.listdir(registry_dir) if f.startswith(model_prefix) and f.endswith(".joblib")]
    if not files:
        return None
    files.sort(reverse=True)
    return os.path.join(registry_dir, files[0])


@click.command()
@click.option("--run-date", default="latest", help="Run date YYYY-MM-DD or 'latest'")
@click.option("--mode", default="full", type=click.Choice(["full", "incremental"]), help="Pipeline mode")
@click.option("--skip-data-gen", is_flag=True, help="Skip synthetic data generation")
@click.option("--config-path", default="config.yaml", help="Path to config.yaml")
@click.option("--output-dir", default="outputs", help="Output directory")
def main(run_date, mode, skip_data_gen, config_path, output_dir):
    """Banking Card Activation & Retention Pipeline."""
    config = load_config(config_path)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(config["data"]["raw_dir"], exist_ok=True)

    if run_date == "latest":
        run_date_dt = datetime.strptime(config["data"]["date_end"], "%Y-%m-%d")
    else:
        run_date_dt = datetime.strptime(run_date, "%Y-%m-%d")
    date_str = run_date_dt.strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"Pipeline run: {date_str} | mode: {mode}")
    print(f"{'='*60}")

    # ── Step 1: Data generation ────────────────────────────────────
    if not skip_data_gen:
        print("\n[1/9] Generating synthetic data...")
        generate(config_path=config_path, output_dir=config["data"]["raw_dir"])
    else:
        print("\n[1/9] Skipping data generation.")

    # ── Step 2: Load & validate data ──────────────────────────────
    print("\n[2/9] Loading and validating data...")
    customers_df, txn_df = load_data(config, output_dir)
    txn_raw = txn_df.copy()  # keep full dataset including post-run_date transactions
    txn_clean, quality_report = validate_transactions(txn_df, customers_df, config, run_date=run_date_dt)
    print(f"  Data quality: {quality_report['clean_count']:,} qualifying transactions "
          f"({quality_report['retention_rate_pct']}% retained)")
    print(f"  Duplicates removed: {quality_report['n_duplicates_removed']}, "
          f"Refunds: {quality_report['n_refunds']}")
    save_data_quality_report(quality_report, output_dir, date_str)

    # ── Step 3: Cohort determination ──────────────────────────────
    print("\n[3/9] Determining cohorts...")
    window = config["activation"]["new_card_window_days"]
    cutoff = run_date_dt - timedelta(days=window)
    activation_customer_ids = set(
        customers_df[
            (customers_df["card_issue_date"] >= cutoff) &
            (customers_df["card_issue_date"] <= run_date_dt)
        ]["customer_id"]
    )
    print(f"  Activation cohort: {len(activation_customer_ids):,} customers (cards issued last {window}d)")
    save_cohort_summary(activation_customer_ids, customers_df, run_date_dt, config, output_dir, date_str)

    # ── Step 4: Feature engineering ───────────────────────────────
    print("\n[4/9] Computing features...")
    mcc_group_map = build_mcc_group_map(config["mcc_groups"])

    activation_features = compute_activation_features(txn_clean, customers_df, run_date_dt, config)
    print(f"  Activation features: {len(activation_features):,} customers × {len(activation_features.columns)} features")

    retention_features = compute_retention_features(
        txn_clean, customers_df, run_date_dt, config, activation_customer_ids,
        future_txn_df=txn_raw,  # pass full txns for prospective label
    )
    print(f"  Retention features: {len(retention_features):,} customers × {len(retention_features.columns)} features")
    save_features(activation_features, retention_features, output_dir, date_str)

    # ── Step 5: Train or load models ──────────────────────────────
    print("\n[5/9] Training/loading models...")
    registry_dir = "models/registry"
    os.makedirs(registry_dir, exist_ok=True)

    act_model = ActivationModel(config)
    ret_model = RetentionModel(config)
    model_metrics = {}

    if mode == "incremental":
        act_path = find_latest_model(registry_dir, "activation_model")
        ret_path = find_latest_model(registry_dir, "retention_model")
        if act_path and ret_path:
            print(f"  Loading existing models: {act_path}")
            act_model.load(act_path)
            ret_model.load(ret_path)
            if act_model.training_metrics:
                model_metrics["activation"] = act_model.training_metrics
                print(f"  Activation model AUC-ROC: {act_model.training_metrics.get('auc_roc', 0):.3f} (from registry)")
            if ret_model.training_metrics:
                model_metrics["retention"] = ret_model.training_metrics
                print(f"  Retention model AUC-ROC: {ret_model.training_metrics.get('auc_roc', 0):.3f} (from registry)")
        else:
            print("  No existing models found, training from scratch...")
            mode = "full"

    if mode == "full":
        labeled_act = activation_features[activation_features["is_activated"].notna()]
        if len(labeled_act) >= 50:
            act_metrics = act_model.train(labeled_act)
            print(f"  Activation model AUC-ROC: {act_metrics['auc_roc']:.3f} | "
                  f"AUC-PR: {act_metrics['auc_pr']:.3f} | "
                  f"train={act_metrics['n_train']}, val={act_metrics['n_val']}")
            act_model.save(registry_dir, version=date_str.replace("-", ""))
            model_metrics["activation"] = act_metrics
        else:
            print(f"  WARNING: Only {len(labeled_act)} labeled activation samples. Need >= 50.")

        labeled_ret = retention_features[retention_features["is_churned"].notna()]
        if len(labeled_ret) >= 50:
            ret_metrics = ret_model.train(labeled_ret)
            print(f"  Retention model AUC-ROC: {ret_metrics['auc_roc']:.3f} | "
                  f"AUC-PR: {ret_metrics['auc_pr']:.3f} | "
                  f"train={ret_metrics['n_train']}, val={ret_metrics['n_val']}")
            ret_model.save(registry_dir, version=date_str.replace("-", ""))
            model_metrics["retention"] = ret_metrics
        else:
            print(f"  WARNING: Only {len(labeled_ret)} labeled retention samples. Need >= 50.")

    # ── Step 5b: Backtesting ──────────────────────────────────────
    backtest_report = run_backtesting(txn_clean, customers_df, act_model, config, run_date_dt)
    if backtest_report.get("cohorts"):
        n_stable = "STABLE" if backtest_report.get("model_stable") else "UNSTABLE"
        avg_auc = backtest_report.get("avg_auc")
        auc_str = f"{avg_auc:.3f}" if avg_auc is not None else "N/A"
        print(f"  Backtesting: {len(backtest_report['cohorts'])} cohorts | avg AUC={auc_str} | {n_stable}")
    backtest_path = os.path.join(output_dir, f"step5_backtesting_{date_str}.json")
    with open(backtest_path, "w") as f:
        import json as _json
        _json.dump(backtest_report, f, indent=2, default=str)

    # ── Step 6: Score + SHAP ──────────────────────────────────────
    print("\n[6/9] Scoring and explaining...")
    shap_top_n = config["models"]["activation"].get("shap_top_n", 3)

    # Activation scoring (all new card customers)
    activation_features_idx = activation_features.set_index("customer_id") if "customer_id" in activation_features.columns else activation_features
    if act_model.model is not None:
        act_scores = act_model.predict_proba(activation_features_idx)
        act_scores_df = pd.DataFrame({
            "customer_id": activation_features_idx.index,
            "ml_probability": act_scores.values,
        })
        act_shap_df = act_model.explain(activation_features_idx, top_n=shap_top_n)
        act_scores_df = act_scores_df.merge(
            activation_features[["customer_id", "customer_segment", "preferred_channel",
                                  "digital_adoption", "dominant_mcc_group", "days_since_card_issue",
                                  "has_recurring_txn"]].fillna(""),
            on="customer_id", how="left",
        )
        act_scores_df["days_since_last_txn"] = act_scores_df.get("days_since_card_issue", 0)
    else:
        act_scores_df = pd.DataFrame()
        act_shap_df = pd.DataFrame()

    # Retention scoring
    retention_features_idx = retention_features.set_index("customer_id") if "customer_id" in retention_features.columns else retention_features
    if ret_model.model is not None:
        ret_scores = ret_model.predict_proba(retention_features_idx)
        ret_scores_df = pd.DataFrame({
            "customer_id": retention_features_idx.index,
            "ml_probability": ret_scores.values,
        })
        ret_shap_df = ret_model.explain(retention_features_idx, top_n=shap_top_n)
        ret_scores_df = ret_scores_df.merge(
            retention_features[["customer_id", "customer_segment", "preferred_channel",
                                  "digital_adoption_30d", "dominant_mcc_group", "days_since_last_txn",
                                  "has_recurring_txn"]].fillna(""),
            on="customer_id", how="left",
        )
        ret_scores_df = ret_scores_df.rename(columns={"digital_adoption_30d": "digital_adoption"})
    else:
        ret_scores_df = pd.DataFrame()
        ret_shap_df = pd.DataFrame()

    # Save scores and SHAP
    save_scores_and_shap(act_scores_df, ret_scores_df, act_shap_df, ret_shap_df, output_dir, date_str)

    # ── Step 6b: Model stability monitoring ───────────────────────
    stability_report = {}
    if act_model.model is not None and act_model.training_feature_stats:
        act_feat_for_psi = activation_features_idx[act_model.feature_cols] if act_model.feature_cols else pd.DataFrame()
        if len(act_feat_for_psi) > 0:
            stability_report = monitor_stability(
                act_feat_for_psi, act_model.training_feature_stats,
                act_model.feature_cols, config["evaluation"].get("psi_alert_threshold", 0.25),
            )
            save_stability_report(stability_report, output_dir, date_str)

    # ── Step 7: Action assignment ──────────────────────────────────
    print("\n[7/9] Assigning actions and generating personalized offers...")
    if len(act_scores_df) > 0 and len(act_shap_df) > 0:
        act_actions = assign_actions(act_scores_df, act_shap_df, "activation", config, date_str)
        act_actions = generate_offers(act_actions, act_scores_df, txn_clean, config, run_date_dt, mcc_group_map)
    else:
        act_actions = pd.DataFrame()

    if len(ret_scores_df) > 0 and len(ret_shap_df) > 0:
        ret_actions = assign_actions(ret_scores_df, ret_shap_df, "retention", config, date_str)
        ret_actions = generate_offers(ret_actions, ret_scores_df, txn_clean, config, run_date_dt, mcc_group_map)
    else:
        ret_actions = pd.DataFrame()

    # ── Step 7b: Fairness check ────────────────────────────────────
    all_scores = pd.concat([
        act_scores_df.assign(model_type="activation") if len(act_scores_df) > 0 else pd.DataFrame(),
        ret_scores_df.assign(model_type="retention") if len(ret_scores_df) > 0 else pd.DataFrame(),
    ], ignore_index=True)
    fairness_report = {}
    if len(all_scores) > 0 and "customer_segment" in all_scores.columns and len(act_actions) > 0:
        merged_for_fairness = all_scores.merge(
            pd.concat([act_actions[["customer_id", "risk_band"]], ret_actions[["customer_id", "risk_band"]]], ignore_index=True),
            on="customer_id", how="left",
        )
        fairness_report = compute_disparity_report(merged_for_fairness.dropna(subset=["risk_band"]))
        print(f"  Fairness check: {fairness_report.get('status', 'unknown')}")
    save_fairness_report(fairness_report, output_dir, date_str)

    # ── Step 8: Evaluation ────────────────────────────────────────
    print("\n[8/9] Running evaluation...")
    all_actions = pd.concat([
        act_actions if len(act_actions) > 0 else pd.DataFrame(),
        ret_actions if len(ret_actions) > 0 else pd.DataFrame(),
    ], ignore_index=True)

    if len(all_actions) > 0:
        eval_report = run_evaluation(all_actions, config, model_metrics, date_str, output_dir)
        print(f"  Validation report written to outputs/validation_report_{date_str}.json")

    # ── Step 9: Write outputs ──────────────────────────────────────
    print("\n[9/9] Writing outputs...")
    if len(act_actions) > 0:
        act_path = os.path.join(output_dir, f"activation_action_list_{date_str}.csv")
        act_actions.to_csv(act_path, index=False)
        print(f"  Activation actions: {len(act_actions):,} customers → {act_path}")

    if len(ret_actions) > 0:
        ret_path = os.path.join(output_dir, f"retention_action_list_{date_str}.csv")
        ret_actions.to_csv(ret_path, index=False)
        print(f"  Retention actions: {len(ret_actions):,} customers → {ret_path}")

    if len(all_actions) > 0:
        schedule = build_campaign_schedule(
            act_actions if len(act_actions) > 0 else pd.DataFrame(),
            ret_actions if len(ret_actions) > 0 else pd.DataFrame(),
            config, run_date_dt, output_dir,
        )
        export_crm_files(schedule, customers_df, config, run_date_dt, output_dir)

    # Feedback ingestion (only if events exist)
    run_feedback_ingestion(
        events_dir=config["pipeline"]["campaign_events_dir"],
        metadata_path=config["pipeline"]["last_run_metadata"],
        run_date=date_str,
        output_dir=output_dir,
    )

    # ── Business report ───────────────────────────────────────────
    report_path = generate_business_report(output_dir, date_str)
    print(f"\n  Business report: {report_path}")

    # Summary
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    if len(act_actions) > 0:
        high_risk_act = (act_actions["risk_band"] == "high_risk").sum()
        print(f"  Activation: {len(act_actions):,} customers | {high_risk_act:,} high-risk")
    if len(ret_actions) > 0:
        high_risk_ret = (ret_actions["risk_band"] == "high_risk").sum()
        print(f"  Retention:  {len(ret_actions):,} customers | {high_risk_ret:,} high-risk")
    if model_metrics:
        for mt, mm in model_metrics.items():
            print(f"  {mt.capitalize()} model AUC-ROC: {mm.get('auc_roc', 0):.3f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
