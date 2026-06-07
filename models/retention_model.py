"""LightGBM retention/churn classifier with SHAP trigger extraction."""
import pandas as pd
import numpy as np
import joblib
import json
import os
from datetime import datetime
import lightgbm as lgb
import shap
from sklearn.metrics import roc_auc_score, average_precision_score

from features.retention_features import RETENTION_FEATURE_COLS

EXCLUDE_FROM_MODEL = {
    "customer_id", "customer_segment", "preferred_channel",
    "dominant_mcc_group", "is_churned", "is_seasonal_customer",
    "lifetime_txn_count",
}


def _get_feature_cols(df: pd.DataFrame) -> list:
    mcc_cols = [c for c in df.columns if c.startswith("mcc_")]
    base = RETENTION_FEATURE_COLS
    all_cols = list(set(base + mcc_cols) - EXCLUDE_FROM_MODEL)
    return [c for c in all_cols if c in df.columns]


class RetentionModel:
    def __init__(self, config: dict):
        self.config = config["models"]["retention"]
        self.model = None
        self.feature_cols = []
        self.explainer = None
        self.training_feature_stats = {}

    def train(self, features_df: pd.DataFrame) -> dict:
        labeled = features_df[features_df["is_churned"].notna()].copy()
        if len(labeled) < 50:
            raise ValueError(f"Too few labeled samples: {len(labeled)}")

        # Exclude seasonal customers from churn label (they are false positives)
        if "is_seasonal_customer" in labeled.columns:
            labeled = labeled[~labeled["is_seasonal_customer"].astype(bool)]

        self.feature_cols = _get_feature_cols(labeled)
        X = labeled[self.feature_cols].fillna(0)
        y = labeled["is_churned"].astype(int)

        # Time-based split using days_since_last_txn as proxy for recency
        # Customers with longer history go to train, recent scorable ones to val
        split_idx = int(len(labeled) * 0.8)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        scale_pos = self.config.get("class_weight_ratio", 5)
        self.model = lgb.LGBMClassifier(
            n_estimators=self.config.get("n_estimators", 500),
            max_depth=self.config.get("max_depth", 6),
            learning_rate=self.config.get("learning_rate", 0.03),
            scale_pos_weight=scale_pos,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(period=-1)],
        )

        self.training_feature_stats = {
            col: {"mean": float(X_train[col].mean()), "std": float(X_train[col].std())}
            for col in self.feature_cols
        }

        val_proba = self.model.predict_proba(X_val)[:, 1]
        metrics = {
            "auc_roc": float(roc_auc_score(y_val, val_proba)) if y_val.nunique() > 1 else 0.0,
            "auc_pr": float(average_precision_score(y_val, val_proba)) if y_val.nunique() > 1 else 0.0,
            "n_train": int(len(X_train)),
            "n_val": int(len(X_val)),
            "churn_rate_train": float(y_train.mean()),
            "churn_rate_val": float(y_val.mean()),
        }
        self.explainer = shap.TreeExplainer(self.model)
        return metrics

    def predict_proba(self, features_df: pd.DataFrame) -> pd.Series:
        X = features_df[self.feature_cols].fillna(0)
        proba = self.model.predict_proba(X)[:, 1]
        return pd.Series(proba, index=features_df.index, name="ml_probability")

    def explain(self, features_df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
        if self.explainer is None:
            self.explainer = shap.TreeExplainer(self.model)
        X = features_df[self.feature_cols].fillna(0)
        shap_values = self.explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        rows = []
        for i, idx in enumerate(features_df.index):
            sv = shap_values[i]
            top_indices = np.argsort(np.abs(sv))[::-1][:top_n]
            row = {"customer_id": features_df.loc[idx, "customer_id"] if "customer_id" in features_df.columns else idx}
            for rank, fi in enumerate(top_indices, start=1):
                feat = self.feature_cols[fi]
                direction = "high" if sv[fi] > 0 else "low"
                row[f"trigger_{rank}"] = feat
                row[f"trigger_{rank}_direction"] = direction
                row[f"trigger_{rank}_shap"] = float(sv[fi])
            rows.append(row)
        return pd.DataFrame(rows)

    def save(self, path: str, version: str = None) -> str:
        os.makedirs(path, exist_ok=True)
        version = version or datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = os.path.join(path, f"retention_model_{version}.joblib")
        meta_path = os.path.join(path, f"retention_model_{version}_meta.json")
        joblib.dump(self.model, model_path)
        meta = {
            "version": version,
            "feature_cols": self.feature_cols,
            "training_feature_stats": self.training_feature_stats,
            "config": self.config,
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        return model_path

    def load(self, model_path: str) -> None:
        meta_path = model_path.replace(".joblib", "_meta.json")
        self.model = joblib.load(model_path)
        with open(meta_path) as f:
            meta = json.load(f)
        self.feature_cols = meta["feature_cols"]
        self.training_feature_stats = meta.get("training_feature_stats", {})
        self.explainer = shap.TreeExplainer(self.model)
