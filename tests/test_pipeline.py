"""End-to-end and unit tests for the banking activation & retention pipeline."""
import os
import sys
import json
import yaml
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_PATH = "config.yaml"

@pytest.fixture(scope="session")
def config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def run_date():
    return datetime(2024, 6, 1)


@pytest.fixture(scope="session")
def small_customers():
    n = 200
    rng = np.random.default_rng(0)
    base_date = datetime(2024, 1, 1)
    card_issue_dates = [base_date + timedelta(days=int(d)) for d in rng.integers(0, 150, n)]
    return pd.DataFrame({
        "customer_id": [f"C{i:04d}" for i in range(n)],
        "card_id": [f"K{i:04d}" for i in range(n)],
        "customer_age": rng.integers(20, 65, n),
        "customer_segment": rng.choice(["premium", "standard", "student"], n),
        "card_issue_date": card_issue_dates,
        "archetype": rng.choice(["never_activated", "slow_activator", "healthy_active",
                                   "declining_active", "high_value", "churned"], n),
        "has_recurring_setup": rng.random(n) > 0.5,
        "recurring_mcc": rng.choice([4900, 4899], n),
        "recurring_merchant": ["ConEd"] * n,
        "consent_sms": [True] * n,
        "consent_email": [True] * n,
        "consent_push": [True] * n,
    })


@pytest.fixture(scope="session")
def small_transactions(small_customers):
    rng = np.random.default_rng(1)
    rows = []
    import uuid
    from datetime import datetime, timedelta
    channels = ["mobile_app", "web", "POS", "ATM"]
    mcc_list = [5411, 5812, 5541, 5814, 4511, 4900, 5600, 7832]
    merchants = ["Kroger", "McDonalds", "Shell", "Starbucks", "Delta", "ConEd", "Gap", "AMC"]
    mcc_merchant = dict(zip(mcc_list, merchants))

    for _, cust in small_customers.iterrows():
        issue_date = cust["card_issue_date"]
        n_txns = rng.integers(0, 30)
        for _ in range(n_txns):
            day_offset = rng.integers(0, 150)
            txn_date = issue_date + timedelta(days=int(day_offset))
            if txn_date > datetime(2024, 6, 1):
                continue
            mcc = int(rng.choice(mcc_list))
            rows.append({
                "transaction_id": str(uuid.uuid4()),
                "customer_id": cust["customer_id"],
                "card_id": cust["card_id"],
                "transaction_date": txn_date,
                "transaction_amount": float(rng.uniform(5, 200)),
                "transaction_type": rng.choice(["purchase", "purchase", "purchase", "refund"], p=[0.85, 0.05, 0.05, 0.05]),
                "merchant_category_code": mcc,
                "merchant_name": mcc_merchant[mcc],
                "channel": rng.choice(channels),
                "net_amount": float(rng.uniform(5, 200)),
                "is_refund": False,
            })
    df = pd.DataFrame(rows)
    if len(df) == 0:
        return pd.DataFrame(columns=["transaction_id","customer_id","card_id","transaction_date",
                                      "transaction_amount","transaction_type","merchant_category_code",
                                      "merchant_name","channel","net_amount","is_refund"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df.sort_values(["customer_id","transaction_date"]).reset_index(drop=True)


# ── Data Validator Tests ─────────────────────────────────────────────────────

class TestDataValidator:
    def test_removes_duplicates(self, small_transactions, small_customers, config):
        from data.data_validator import validate_transactions
        duped = pd.concat([small_transactions, small_transactions.iloc[:10]], ignore_index=True)
        clean, report = validate_transactions(duped, small_customers, config, datetime(2024, 6, 1))
        assert report["n_duplicates_removed"] == 10

    def test_removes_future_transactions(self, small_transactions, small_customers, config):
        from data.data_validator import validate_transactions
        future = small_transactions.copy()
        future.loc[0, "transaction_date"] = datetime(2025, 1, 1)
        clean, report = validate_transactions(future, small_customers, config, datetime(2024, 6, 1))
        assert report["n_future_removed"] >= 1

    def test_removes_excluded_types(self, small_transactions, small_customers, config):
        from data.data_validator import validate_transactions
        txn_with_internal = small_transactions.copy()
        txn_with_internal.loc[txn_with_internal.index[0], "transaction_type"] = "internal"
        clean, report = validate_transactions(txn_with_internal, small_customers, config, datetime(2024, 6, 1))
        assert "internal" not in clean["transaction_type"].values

    def test_returns_quality_report(self, small_transactions, small_customers, config):
        from data.data_validator import validate_transactions
        clean, report = validate_transactions(small_transactions, small_customers, config, datetime(2024, 6, 1))
        assert "original_count" in report
        assert "clean_count" in report
        assert "retention_rate_pct" in report
        assert report["retention_rate_pct"] <= 100.0


# ── Feature Engineering Tests ────────────────────────────────────────────────

class TestActivationFeatures:
    def test_returns_dataframe(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        assert isinstance(feats, pd.DataFrame)

    def test_has_required_columns(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No activation cohort in this date range")
        assert "customer_id" in feats.columns
        assert "days_since_card_issue" in feats.columns
        assert "first_transaction_day" in feats.columns
        assert "digital_adoption" in feats.columns

    def test_first_transaction_day_imputed_correctly(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No activation cohort")
        # Never-transacted customers should have first_transaction_day = 999
        assert (feats["first_transaction_day"] <= 999).all()
        assert (feats["first_transaction_day"] >= 0).all()

    def test_has_mcc_group_features(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No activation cohort")
        mcc_cols = [c for c in feats.columns if c.startswith("mcc_")]
        assert len(mcc_cols) > 0, "Expected MCC group feature columns"

    def test_no_data_leakage_in_activation_label(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No activation cohort")
        # Customers within first 60 days should have NaN label (not labeled)
        early = feats[feats["days_since_card_issue"] < 60]
        assert early["is_activated"].isna().all(), \
            "Customers within 60 days should not be labeled (right-censoring)"


class TestRetentionFeatures:
    def test_returns_dataframe(self, small_transactions, small_customers, config, run_date):
        from features.retention_features import compute_retention_features
        feats = compute_retention_features(small_transactions, small_customers, run_date, config)
        assert isinstance(feats, pd.DataFrame)

    def test_has_velocity_features(self, small_transactions, small_customers, config, run_date):
        from features.retention_features import compute_retention_features
        feats = compute_retention_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No retention cohort")
        assert "txn_velocity_change" in feats.columns
        assert "spend_velocity_change" in feats.columns

    def test_velocity_clamped(self, small_transactions, small_customers, config, run_date):
        from features.retention_features import compute_retention_features
        feats = compute_retention_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No retention cohort")
        assert (feats["txn_velocity_change"] >= -1).all()
        assert (feats["txn_velocity_change"] <= 5).all()

    def test_has_mcc_group_velocity_features(self, small_transactions, small_customers, config, run_date):
        from features.retention_features import compute_retention_features
        feats = compute_retention_features(small_transactions, small_customers, run_date, config)
        if len(feats) == 0:
            pytest.skip("No retention cohort")
        vel_cols = [c for c in feats.columns if "velocity" in c and "mcc_" in c]
        assert len(vel_cols) > 0, "Expected MCC group velocity columns"

    def test_disjoint_from_activation_cohort(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        from features.retention_features import compute_retention_features
        act_feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        activation_ids = set(act_feats["customer_id"]) if len(act_feats) > 0 else set()
        ret_feats = compute_retention_features(small_transactions, small_customers, run_date, config, activation_ids)
        if len(ret_feats) == 0:
            pytest.skip("No retention cohort")
        overlap = activation_ids & set(ret_feats["customer_id"])
        assert len(overlap) == 0, f"Cohorts overlap: {len(overlap)} shared customers"


# ── Model Tests ──────────────────────────────────────────────────────────────

class TestActivationModel:
    def test_train_and_predict(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        from models.activation_model import ActivationModel
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        labeled = feats[feats["is_activated"].notna()]
        if len(labeled) < 50:
            pytest.skip(f"Only {len(labeled)} labeled samples, need 50")
        model = ActivationModel(config)
        metrics = model.train(labeled)
        assert "auc_roc" in metrics
        assert 0 <= metrics["auc_roc"] <= 1
        proba = model.predict_proba(feats.set_index("customer_id"))
        assert len(proba) == len(feats)
        assert (proba >= 0).all() and (proba <= 1).all()

    def test_explain_returns_triggers(self, small_transactions, small_customers, config, run_date):
        from features.activation_features import compute_activation_features
        from models.activation_model import ActivationModel
        feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        labeled = feats[feats["is_activated"].notna()]
        if len(labeled) < 50:
            pytest.skip(f"Only {len(labeled)} labeled samples")
        model = ActivationModel(config)
        model.train(labeled)
        shap_df = model.explain(feats.set_index("customer_id"), top_n=3)
        assert "trigger_1" in shap_df.columns
        assert "trigger_1_direction" in shap_df.columns
        assert len(shap_df) == len(feats)


class TestRetentionModel:
    def test_train_and_predict(self, small_transactions, small_customers, config, run_date):
        from features.retention_features import compute_retention_features
        from models.retention_model import RetentionModel
        from features.activation_features import compute_activation_features
        act_feats = compute_activation_features(small_transactions, small_customers, run_date, config)
        act_ids = set(act_feats["customer_id"]) if len(act_feats) > 0 else set()
        feats = compute_retention_features(small_transactions, small_customers, run_date, config, act_ids)
        labeled = feats[feats["is_churned"].notna()]
        if len(labeled) < 50:
            pytest.skip(f"Only {len(labeled)} labeled samples, need 50")
        model = RetentionModel(config)
        metrics = model.train(labeled)
        assert "auc_roc" in metrics
        proba = model.predict_proba(feats.set_index("customer_id"))
        assert len(proba) == len(feats)


# ── Action Engine Tests ──────────────────────────────────────────────────────

class TestActionEngine:
    def _make_scores(self, n=10):
        rng = np.random.default_rng(42)
        return pd.DataFrame({
            "customer_id": [f"C{i:04d}" for i in range(n)],
            "ml_probability": rng.uniform(0, 1, n),
            "customer_segment": ["standard"] * n,
            "preferred_channel": ["mobile_app"] * n,
            "digital_adoption": [0.6] * n,
            "has_recurring_txn": [1] * n,
            "days_since_last_txn": [30] * n,
        })

    def _make_shap(self, n=10):
        return pd.DataFrame({
            "customer_id": [f"C{i:04d}" for i in range(n)],
            "trigger_1": ["txn_velocity_change"] * n,
            "trigger_1_direction": ["low"] * n,
            "trigger_1_shap": [-0.8] * n,
            "trigger_2": ["days_since_last_txn"] * n,
            "trigger_2_direction": ["high"] * n,
            "trigger_2_shap": [0.5] * n,
            "trigger_3": ["digital_adoption"] * n,
            "trigger_3_direction": ["low"] * n,
            "trigger_3_shap": [-0.3] * n,
        })

    def test_assign_actions_returns_dataframe(self, config):
        from actions.action_engine import assign_actions
        scores = self._make_scores()
        shap = self._make_shap()
        result = assign_actions(scores, shap, "retention", config)
        assert isinstance(result, pd.DataFrame)
        assert "risk_band" in result.columns
        assert "priority_score" in result.columns

    def test_risk_bands_are_valid(self, config):
        from actions.action_engine import assign_actions
        scores = self._make_scores(100)
        shap = pd.DataFrame({"customer_id": scores["customer_id"]})
        result = assign_actions(scores, shap, "retention", config)
        assert set(result["risk_band"]).issubset({"high_risk", "medium_risk", "low_risk"})

    def test_sorted_by_priority(self, config):
        from actions.action_engine import assign_actions
        scores = self._make_scores(50)
        shap = pd.DataFrame({"customer_id": scores["customer_id"]})
        result = assign_actions(scores, shap, "activation", config)
        assert (result["priority_score"].diff().dropna() <= 0).all(), \
            "Output should be sorted by priority_score descending"

    def test_high_priority_premium_customers(self, config):
        from actions.action_engine import assign_actions, compute_priority_score
        # Premium customer with high churn probability should have higher priority than
        # standard customer with same probability
        p_prem = compute_priority_score(0.8, "premium", "retention", 50, config)
        p_std = compute_priority_score(0.8, "standard", "retention", 50, config)
        assert p_prem > p_std


# ── Offer Generator Tests ────────────────────────────────────────────────────

class TestOfferGenerator:
    def test_generates_specific_action(self, small_transactions, config):
        from actions.offer_generator import _render_offer_action
        action = _render_offer_action(
            "grocery", "high_risk", 60,
            config["actions"]["offer_action_templates"],
        )
        assert isinstance(action, str)
        assert len(action) > 0
        assert "grocery" in action.lower() or "card" in action.lower()

    def test_all_categories_render(self, config):
        from actions.offer_generator import _render_offer_action
        templates = config["actions"]["offer_action_templates"]
        for category in templates:
            action = _render_offer_action(
                category, "medium_risk", 30,
                templates,
            )
            assert isinstance(action, str)
            assert len(action) > 0


# ── Evaluation Tests ─────────────────────────────────────────────────────────

class TestMetrics:
    def test_compute_model_metrics(self):
        from evaluation.metrics import compute_model_metrics
        y_true = pd.Series([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        y_prob = pd.Series([0.1, 0.8, 0.2, 0.9, 0.3, 0.7, 0.15, 0.85, 0.25, 0.75])
        metrics = compute_model_metrics(y_true, y_prob)
        assert metrics["auc_roc"] > 0.8
        assert 0 <= metrics["precision"] <= 1
        assert 0 <= metrics["recall"] <= 1
        assert "lift_at_top_10pct" in metrics

    def test_compute_lift(self):
        from evaluation.metrics import compute_lift_at_k
        y_true = pd.Series([1, 1, 1, 0, 0, 0, 0, 0, 0, 0])  # top 30% are all positives
        y_prob = pd.Series([0.9, 0.8, 0.7, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1])
        lift = compute_lift_at_k(y_true, y_prob, k=0.30)
        assert lift > 1.0, "Top 30% should have lift > 1"


class TestPowerAnalysis:
    def test_returns_required_sample_size(self):
        from evaluation.power_analysis import compute_required_sample_size
        result = compute_required_sample_size(0.12, 0.03)
        assert result["n_control"] > 0
        assert result["n_treatment"] > result["n_control"]
        assert 0 < result["holdout_fraction"] < 1

    def test_sufficient_power_check(self):
        from evaluation.power_analysis import check_sufficient_power
        result = check_sufficient_power(100000, 0.12, 0.03)
        assert "is_sufficient" in result
        assert "recommendation" in result


class TestFairnessCheck:
    def test_no_violation(self):
        from features.fairness_check import compute_disparity_report
        df = pd.DataFrame({
            "customer_segment": ["premium"] * 50 + ["standard"] * 100 + ["student"] * 50,
            "risk_band": (["high_risk"] * 10 + ["medium_risk"] * 40 +
                          ["high_risk"] * 20 + ["medium_risk"] * 80 +
                          ["high_risk"] * 10 + ["medium_risk"] * 40),
        })
        report = compute_disparity_report(df)
        assert "status" in report

    def test_detects_violation(self):
        from features.fairness_check import compute_disparity_report
        df = pd.DataFrame({
            "customer_segment": ["premium"] * 100 + ["student"] * 100,
            "risk_band": (["high_risk"] * 5 + ["low_risk"] * 95 +
                          ["high_risk"] * 80 + ["low_risk"] * 20),
        })
        report = compute_disparity_report(df)
        # premium has 5% adverse rate, student has 80% — ratio is 5/80 = 6.25% < 80%
        assert report["status"] == "violation"


class TestBanditOptimizer:
    def test_cold_start_samples_uniformly(self, tmp_path):
        from actions.bandit_optimizer import BanditOptimizer
        offers = ["cashback", "points_multiplier", "statement_credit"]
        bandit = BanditOptimizer(offers, state_path=str(tmp_path / "bandit.json"))
        selections = [bandit.select_offer_type("retention_high_risk", "high_risk") for _ in range(100)]
        # With uniform prior, all offers should be selected at least once
        assert len(set(selections)) > 1

    def test_learns_from_feedback(self, tmp_path):
        from actions.bandit_optimizer import BanditOptimizer
        offers = ["cashback", "points_multiplier"]
        bandit = BanditOptimizer(offers, state_path=str(tmp_path / "bandit2.json"))
        # Strongly reward cashback
        for _ in range(50):
            bandit.update("bucket_a", "high_risk", "cashback", redeemed=True)
            bandit.update("bucket_a", "high_risk", "points_multiplier", redeemed=False)
        selections = [bandit.select_offer_type("bucket_a", "high_risk") for _ in range(20)]
        cashback_pct = selections.count("cashback") / len(selections)
        assert cashback_pct > 0.6, "After many positive updates, cashback should dominate"


# ── Integration Test ─────────────────────────────────────────────────────────

class TestIntegration:
    def test_output_files_exist_after_pipeline(self):
        """Check that pipeline outputs were generated."""
        output_dir = "outputs"
        if not os.path.exists(output_dir):
            pytest.skip("Outputs directory not found — run pipeline first")

        # Check for at least one action list
        csv_files = [f for f in os.listdir(output_dir) if f.endswith(".csv")]
        assert len(csv_files) > 0, "Expected CSV output files from pipeline"

    def test_action_list_schema(self):
        """Verify action list has required columns."""
        output_dir = "outputs"
        import glob
        files = glob.glob(os.path.join(output_dir, "activation_action_list_*.csv"))
        if not files:
            pytest.skip("No activation action list found")
        df = pd.read_csv(files[-1])
        required_cols = ["customer_id", "risk_band", "priority_score", "ml_probability",
                         "offer_category", "specific_action", "primary_channel"]
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"

    def test_campaign_schedule_schema(self):
        """Verify campaign schedule has required columns."""
        output_dir = "outputs"
        import glob
        files = glob.glob(os.path.join(output_dir, "campaign_schedule_*.csv"))
        if not files:
            pytest.skip("No campaign schedule found")
        df = pd.read_csv(files[-1])
        required = ["customer_id", "campaign_id", "channel", "scheduled_date", "touch_number"]
        for col in required:
            assert col in df.columns, f"Missing: {col}"

    def test_validation_report_has_roi_table(self):
        """Verify validation report includes ROI comparison table."""
        output_dir = "outputs"
        import glob
        files = glob.glob(os.path.join(output_dir, "validation_report_*.json"))
        if not files:
            pytest.skip("No validation report found")
        with open(files[-1]) as f:
            report = json.load(f)
        assert "roi_comparison_table" in report
        assert isinstance(report["roi_comparison_table"], list)
        assert len(report["roi_comparison_table"]) > 0
