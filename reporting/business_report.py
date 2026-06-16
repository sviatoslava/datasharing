"""Generate self-contained HTML business report from pipeline outputs."""
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime


# ---------------------------------------------------------------------------
# CSS + layout constants
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --navy: #1a3a5c;
  --navy-light: #2d5f8a;
  --grey: #f5f7fa;
  --grey-dark: #6b7280;
  --green: #16a34a;
  --amber: #d97706;
  --red: #dc2626;
  --white: #ffffff;
  --border: #e5e7eb;
}
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: var(--grey); color: #1f2937; }
nav { background: var(--navy); padding: 12px 24px; position: sticky; top: 0; z-index: 100; }
nav a { color: #cbd5e1; text-decoration: none; margin-right: 16px; font-size: 13px; }
nav a:hover { color: white; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
section { background: white; border-radius: 8px; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
h1 { color: var(--navy); margin: 0; font-size: 28px; }
h2 { color: var(--navy); border-bottom: 2px solid var(--navy); padding-bottom: 8px; margin-top: 0; }
h3 { color: var(--navy-light); }
.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0; }
.kpi-tile { background: var(--navy); color: white; border-radius: 8px; padding: 20px; text-align: center; }
.kpi-tile .value { font-size: 32px; font-weight: bold; }
.kpi-tile .label { font-size: 13px; color: #cbd5e1; margin-top: 4px; }
.kpi-tile.green { background: var(--green); }
.kpi-tile.amber { background: var(--amber); }
table { width: 100%; border-collapse: collapse; font-size: 14px; margin: 12px 0; }
th { background: var(--navy); color: white; padding: 10px 12px; text-align: left; }
td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
tr:nth-child(even) { background: var(--grey); }
.badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
.badge-green { background: #dcfce7; color: var(--green); }
.badge-amber { background: #fef3c7; color: var(--amber); }
.badge-red { background: #fee2e2; color: var(--red); }
.callout { border-left: 4px solid var(--amber); background: #fef9f0; padding: 12px 16px; margin: 12px 0; font-size: 13px; border-radius: 0 6px 6px 0; }
.callout-red { border-color: var(--red); background: #fff5f5; }
.action-box { border: 2px solid var(--navy); border-radius: 6px; padding: 16px; margin: 12px 0; }
.action-box h4 { margin: 0 0 8px; color: var(--navy); }
pre { background: #f1f5f9; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; }
.header-bar { background: var(--navy); color: white; padding: 24px; margin-bottom: 0; border-radius: 8px 8px 0 0; }
@media print { nav { display: none; } body { background: white; } section { box-shadow: none; break-inside: avoid; } }
"""

_NAV_LINKS = [
    ("s1", "Executive Summary"),
    ("s2", "Model Accuracy & Backtesting"),
    ("s3", "Aggregated Audience View"),
    ("s4", "Sample Customers"),
    ("s5", "Campaign Briefs"),
    ("s6", "Offer Portfolio"),
    ("s7", "Channel Distribution"),
    ("s8", "Compliance & Fairness"),
    ("s9", "Action Items"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_int(v) -> str:
    try:
        return f"{int(v):,}"
    except Exception:
        return str(v)


def _fmt_float(v, decimals: int = 3) -> str:
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return str(v)


def _badge(text: str, colour: str) -> str:
    """colour: green | amber | red"""
    return f'<span class="badge badge-{colour}">{text}</span>'


def _callout(text: str, red: bool = False) -> str:
    cls = "callout callout-red" if red else "callout"
    return f'<div class="{cls}">{text}</div>'


def _html_table(headers: list, rows: list) -> str:
    """Build a plain HTML table from header list and list-of-lists rows."""
    th_cells = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        td_cells = "".join(f"<td>{cell}</td>" for cell in row)
        body += f"<tr>{td_cells}</tr>"
    return f"<table><thead><tr>{th_cells}</tr></thead><tbody>{body}</tbody></table>"


def _df_to_html_table(df: pd.DataFrame, max_rows: int = 200) -> str:
    if df is None or len(df) == 0:
        return "<p><em>No data available.</em></p>"
    subset = df.head(max_rows)
    headers = list(subset.columns)
    rows = [list(r) for r in subset.itertuples(index=False)]
    return _html_table(headers, rows)


def _safe_auc_badge(val) -> str:
    try:
        f = float(val)
        if f >= 0.75:
            return f'{_fmt_float(f)} {_badge("Good", "green")}'
        return f'{_fmt_float(f)} {_badge("Below target", "amber")}'
    except Exception:
        return str(val)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _load_parquet(path: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _load_csv(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_all(output_dir: str, date_str: str) -> dict:
    p = lambda name: os.path.join(output_dir, name)
    return {
        "quality_report":   _load_json(p(f"step2_data_quality_{date_str}.json")),
        "cohort_summary":   _load_json(p(f"step3_cohort_summary_{date_str}.json")),
        "feature_summary":  _load_json(p(f"step4_feature_summary_{date_str}.json")),
        "act_scores":       _load_parquet(p(f"step6_activation_scores_{date_str}.parquet")),
        "ret_scores":       _load_parquet(p(f"step6_retention_scores_{date_str}.parquet")),
        "shap_df":          _load_parquet(p(f"step6_shap_explanations_{date_str}.parquet")),
        "fairness_report":  _load_json(p(f"step6b_fairness_report_{date_str}.json")),
        "val_report":       _load_json(p(f"validation_report_{date_str}.json")),
        "stability_report": _load_json(p(f"stability_report_{date_str}.json")),
        "act_actions":      _load_csv(p(f"activation_action_list_{date_str}.csv")),
        "ret_actions":      _load_csv(p(f"retention_action_list_{date_str}.csv")),
        "backtest_report":  _load_json(p(f"step5_backtesting_{date_str}.json")),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_executive_summary(d: dict, run_date: str) -> str:
    act_scores    = d["act_scores"]
    ret_scores    = d["ret_scores"]
    cohort        = d["cohort_summary"]
    val_report    = d["val_report"]
    act_actions   = d["act_actions"]
    ret_actions   = d["ret_actions"]

    # KPI values
    new_cards_scored = len(act_scores) if len(act_scores) > 0 else cohort.get("activation_cohort_size", 0)
    active_scored    = len(ret_scores) if len(ret_scores) > 0 else cohort.get("retention_cohort_size", 0)

    act_auc_raw = val_report.get("activation", {}).get("auc_roc",
                  val_report.get("model_metrics", {}).get("activation", {}).get("auc_roc", "N/A"))
    ret_auc_raw = val_report.get("retention", {}).get("auc_roc",
                  val_report.get("model_metrics", {}).get("retention", {}).get("auc_roc", "N/A"))

    def _auc_tile_class(val):
        try:
            return "green" if float(val) >= 0.75 else "amber"
        except Exception:
            return ""

    total_targeted = len(act_actions) + len(ret_actions)

    def _count_high_risk(df: pd.DataFrame) -> int:
        if df is None or len(df) == 0 or "risk_band" not in df.columns:
            return 0
        return int((df["risk_band"] == "high_risk").sum())

    high_risk_alerts = _count_high_risk(act_actions) + _count_high_risk(ret_actions)

    def _tile(value_html: str, label: str, extra_cls: str = "") -> str:
        cls = f"kpi-tile {extra_cls}".strip()
        return (
            f'<div class="{cls}">'
            f'<div class="value">{value_html}</div>'
            f'<div class="label">{label}</div>'
            f'</div>'
        )

    act_auc_disp = _fmt_float(act_auc_raw) if act_auc_raw != "N/A" else "N/A"
    ret_auc_disp = _fmt_float(ret_auc_raw) if ret_auc_raw != "N/A" else "N/A"

    tiles = (
        _tile(_fmt_int(new_cards_scored), "New Cards Scored") +
        _tile(_fmt_int(active_scored),    "Active Customers Scored") +
        _tile(act_auc_disp, "Activation Model AUC", _auc_tile_class(act_auc_raw)) +
        _tile(ret_auc_disp, "Retention Model AUC",  _auc_tile_class(ret_auc_raw)) +
        _tile(_fmt_int(total_targeted),  "Total Customers Targeted") +
        _tile(_fmt_int(high_risk_alerts), "High-Risk Alerts", "amber" if high_risk_alerts > 0 else "")
    )

    summary_para = (
        "This report summarises the Banking Card Activation &amp; Retention pipeline run "
        f"for <strong>{run_date}</strong>. "
        f"The activation model scored <strong>{_fmt_int(new_cards_scored)}</strong> newly issued "
        "cardholders to identify those at risk of not activating within 90 days. "
        f"The retention model assessed <strong>{_fmt_int(active_scored)}</strong> existing customers "
        "for churn risk. "
        f"In total, <strong>{_fmt_int(total_targeted)}</strong> customers have been assigned targeted "
        "outreach actions, of whom <strong>{}</strong> are classified as high-risk and require "
        "immediate intervention.".format(_fmt_int(high_risk_alerts))
    )

    header = (
        '<div class="header-bar">'
        '<h1>Banking Card Activation &amp; Retention Pipeline</h1>'
        f'<p style="margin:8px 0 0;color:#cbd5e1;font-size:14px;">Run date: {run_date}</p>'
        '</div>'
    )

    return (
        f'<section id="s1" style="padding:0;overflow:hidden;">'
        f'{header}'
        f'<div style="padding:24px;">'
        f'<div class="kpi-grid">{tiles}</div>'
        f'<p>{summary_para}</p>'
        f'</div>'
        f'</section>'
    )


def _section_model_accuracy(d: dict) -> str:
    val_report      = d["val_report"]
    backtest_report = d["backtest_report"]

    # Pull metrics — support both flat and nested layouts produced by the pipeline
    def _get_model_metrics(report: dict, model_key: str) -> dict:
        # Direct key (step_outputs style)
        if model_key in report:
            return report[model_key]
        # Nested under model_metrics (campaign_evaluator style)
        return report.get("model_metrics", {}).get(model_key, {})

    act_m = _get_model_metrics(val_report, "activation")
    ret_m = _get_model_metrics(val_report, "retention")

    def _v(metrics: dict, key: str) -> str:
        v = metrics.get(key, "N/A")
        if v == "N/A" or v is None:
            return "N/A"
        try:
            return _fmt_float(float(v))
        except Exception:
            return str(v)

    metric_rows = [
        ["AUC-ROC",        _v(act_m, "auc_roc"),           _v(ret_m, "auc_roc"),           "Higher is better; target ≥ 0.75"],
        ["AUC-PR",         _v(act_m, "auc_pr"),            _v(ret_m, "auc_pr"),            "More informative on imbalanced classes"],
        ["Precision",      _v(act_m, "precision"),         _v(ret_m, "precision"),         "Of customers flagged, % correctly identified"],
        ["Recall",         _v(act_m, "recall"),            _v(ret_m, "recall"),            "Of true at-risk customers, % captured"],
        ["Lift @ Top 10%", _v(act_m, "lift_at_top_10pct"), _v(ret_m, "lift_at_top_10pct"), "How many times better than random targeting"],
    ]

    metrics_table = _html_table(
        ["Metric", "Activation Model", "Retention Model", "Interpretation"],
        metric_rows,
    )

    # Backtesting subsection
    cohorts = backtest_report.get("cohorts", [])
    backtest_html = ""
    if cohorts:
        bt_rows = []
        for c in cohorts:
            miss = c.get("miss_rate")
            miss_str = _fmt_float(miss) if miss is not None else "N/A"
            auc_str  = _fmt_float(c.get("auc")) if c.get("auc") is not None else "N/A"
            bt_rows.append([
                c.get("cohort_label", ""),
                _fmt_int(c.get("n_customers", 0)),
                auc_str,
                _fmt_int(c.get("n_predicted_nonactivating", 0)),
                _fmt_int(c.get("n_actual_nonactivating", 0)),
                miss_str,
            ])
        stable = backtest_report.get("model_stable", False)
        stable_badge = _badge("STABLE", "green") if stable else _badge("UNSTABLE", "red")
        backtest_html = (
            f'<h3>Backtesting Results <span style="font-weight:normal;font-size:14px;">Stability: {stable_badge}</span></h3>'
            + _html_table(
                ["Cohort", "N Customers", "AUC", "Predicted Non-Activating",
                 "Actual Non-Activating", "Miss Rate"],
                bt_rows,
            )
        )

    callout = _callout(
        "<strong>VP Data Science note:</strong> AUC is a discrimination metric, not a business guarantee. "
        "Lift at the top decile is more actionable — it tells you how much better targeted outreach "
        "performs vs. random."
    )

    return (
        f'<section id="s2">'
        f'<h2>Model Accuracy &amp; Backtesting</h2>'
        f'{metrics_table}'
        f'{backtest_html}'
        f'{callout}'
        f'</section>'
    )


def _audience_pivot(df: pd.DataFrame, title: str) -> str:
    """Pivot segment × risk_band count table as HTML."""
    if df is None or len(df) == 0:
        return f"<h3>{title}</h3><p><em>No data available.</em></p>"
    if "customer_segment" not in df.columns or "risk_band" not in df.columns:
        return f"<h3>{title}</h3><p><em>Segment or risk_band column not present.</em></p>"
    try:
        pivot = (
            df.groupby(["customer_segment", "risk_band"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        pivot.columns.name = None
        return f"<h3>{title}</h3>" + _df_to_html_table(pivot)
    except Exception as exc:
        return f"<h3>{title}</h3><p><em>Could not build pivot: {exc}</em></p>"


def _section_audience(d: dict) -> str:
    act_scores = d["act_scores"]
    ret_scores = d["ret_scores"]
    act_actions = d["act_actions"]
    ret_actions = d["ret_actions"]
    shap_df     = d["shap_df"]

    # Use actions (which carry risk_band) if scores don't have it
    act_df = act_scores if (len(act_scores) > 0 and "risk_band" in act_scores.columns) else act_actions
    ret_df = ret_scores if (len(ret_scores) > 0 and "risk_band" in ret_scores.columns) else ret_actions

    act_pivot = _audience_pivot(act_df, "3a. Activation Audience — Segment × Risk Band")
    ret_pivot = _audience_pivot(ret_df, "3b. Retention Audience — Segment × Risk Band")

    # Top SHAP triggers
    shap_html = ""
    if shap_df is not None and len(shap_df) > 0 and "top_feature_1" in shap_df.columns:
        counts = (
            shap_df["top_feature_1"]
            .value_counts()
            .head(5)
            .reset_index()
        )
        counts.columns = ["Feature", "Count"]
        counts["% of Customers"] = (counts["Count"] / len(shap_df) * 100).map(lambda x: f"{x:.1f}%")
        shap_html = (
            "<h3>3c. Top Triggers Driving Risk</h3>"
            + _df_to_html_table(counts)
        )
    elif shap_df is not None and len(shap_df) > 0 and "trigger_1" in shap_df.columns:
        # Alternative column name used by the explain() output
        counts = (
            shap_df["trigger_1"]
            .value_counts()
            .head(5)
            .reset_index()
        )
        counts.columns = ["Feature", "Count"]
        counts["% of Customers"] = (counts["Count"] / len(shap_df) * 100).map(lambda x: f"{x:.1f}%")
        shap_html = (
            "<h3>3c. Top Triggers Driving Risk</h3>"
            + _df_to_html_table(counts)
        )

    return (
        f'<section id="s3">'
        f'<h2>Aggregated Audience View</h2>'
        f'{act_pivot}'
        f'{ret_pivot}'
        f'{shap_html}'
        f'</section>'
    )


def _sample_action_table(df: pd.DataFrame, model_label: str) -> str:
    if df is None or len(df) == 0:
        return f"<p><em>No {model_label} action data available.</em></p>"

    cols_wanted = [
        "customer_id", "customer_segment", "risk_band", "ml_probability",
        "offer_category", "specific_action", "primary_channel", "first_scheduled_send",
    ]
    cols_present = [c for c in cols_wanted if c in df.columns]

    high_risk = df[df["risk_band"] == "high_risk"].head(5) if "risk_band" in df.columns else pd.DataFrame()
    med_risk  = df[df["risk_band"] == "medium_risk"].head(5) if "risk_band" in df.columns else pd.DataFrame()
    sample    = pd.concat([high_risk, med_risk], ignore_index=True)

    if len(sample) == 0:
        sample = df.head(10)

    if len(cols_present) == 0:
        return f"<p><em>Expected columns not found in {model_label} action list.</em></p>"

    return f"<h3>{model_label} — Sample Customers</h3>" + _df_to_html_table(sample[cols_present])


def _section_sample_customers(d: dict) -> str:
    act_actions = d["act_actions"]
    ret_actions = d["ret_actions"]

    act_html = _sample_action_table(act_actions, "Activation")
    ret_html = _sample_action_table(ret_actions, "Retention")

    note = _callout(
        "Offer value (cashback %, points multiplier) to be set by marketing team based on "
        "segment budget guidelines."
    )

    return (
        f'<section id="s4">'
        f'<h2>Sample Customers</h2>'
        f'{act_html}'
        f'{ret_html}'
        f'{note}'
        f'</section>'
    )


def _brief_box(title: str, lines: list) -> str:
    body = "\n".join(lines)
    return (
        f'<div class="action-box">'
        f'<h4>{title}</h4>'
        f'<pre>{body}</pre>'
        f'</div>'
    )


def _channel_dist_text(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0 or "primary_channel" not in df.columns:
        return "  Channels: N/A"
    counts = df["primary_channel"].value_counts()
    parts = [f"{ch}: {n:,}" for ch, n in counts.items()]
    return "  Channels: " + ", ".join(parts)


def _category_dist_text(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0 or "offer_category" not in df.columns:
        return "  Offer categories: N/A"
    counts = df["offer_category"].value_counts().head(5)
    parts = [f"{cat}: {n:,}" for cat, n in counts.items()]
    return "  Categories: " + ", ".join(parts)


def _section_campaign_briefs(d: dict) -> str:
    act_actions = d["act_actions"]
    ret_actions = d["ret_actions"]

    def _high_risk_count(df):
        if df is None or len(df) == 0 or "risk_band" not in df.columns:
            return 0
        return int((df["risk_band"] == "high_risk").sum())

    act_hr = _high_risk_count(act_actions)
    ret_hr = _high_risk_count(ret_actions)

    brief1_lines = [
        f"Campaign:          Activation — High Risk",
        f"Target audience:   {_fmt_int(act_hr)} newly issued cardholders at high risk of non-activation",
        _channel_dist_text(act_actions[act_actions["risk_band"] == "high_risk"] if "risk_band" in (act_actions.columns if act_actions is not None and len(act_actions) > 0 else pd.DataFrame().columns) else act_actions),
        _category_dist_text(act_actions[act_actions["risk_band"] == "high_risk"] if "risk_band" in (act_actions.columns if act_actions is not None and len(act_actions) > 0 else pd.DataFrame().columns) else act_actions),
        f"Offer duration:    60 days (premium/standard), 30 days (student)",
        f"Frequency:         3 touches per week for high-risk",
        f"Budget:            TBD by marketing team",
        f"A/B holdout:       20% control group required",
    ]

    brief2_lines = [
        f"Campaign:          Retention — High Risk",
        f"Target audience:   {_fmt_int(ret_hr)} active customers at high churn risk",
        _channel_dist_text(ret_actions[ret_actions["risk_band"] == "high_risk"] if "risk_band" in (ret_actions.columns if ret_actions is not None and len(ret_actions) > 0 else pd.DataFrame().columns) else ret_actions),
        _category_dist_text(ret_actions[ret_actions["risk_band"] == "high_risk"] if "risk_band" in (ret_actions.columns if ret_actions is not None and len(ret_actions) > 0 else pd.DataFrame().columns) else ret_actions),
        f"Offer duration:    60 days (premium/standard), 30 days (student)",
        f"Frequency:         3 touches per week for high-risk; urgency hook for >45d inactive",
        f"Budget:            TBD by marketing team",
        f"A/B holdout:       20% control group required",
    ]

    return (
        f'<section id="s5">'
        f'<h2>Example Campaign Briefs</h2>'
        + _brief_box("Brief 1 — Activation High-Risk", brief1_lines)
        + _brief_box("Brief 2 — Retention High-Risk", brief2_lines)
        + '</section>'
    )


def _section_offer_portfolio(d: dict) -> str:
    val_report  = d["val_report"]
    act_actions = d["act_actions"]
    ret_actions = d["ret_actions"]

    portfolio_html = ""

    roi_data = val_report.get("roi_comparison_table") or val_report.get("roi_comparison")
    if roi_data and isinstance(roi_data, list) and len(roi_data) > 0:
        headers = list(roi_data[0].keys())
        rows = [[str(row.get(h, "")) for h in headers] for row in roi_data]
        portfolio_html = "<h3>ROI Comparison (Model-Estimated)</h3>" + _html_table(headers, rows)
    else:
        # Fall back to offer_category distribution
        act_cats = {}
        ret_cats = {}
        if act_actions is not None and len(act_actions) > 0 and "offer_category" in act_actions.columns:
            act_cats = act_actions["offer_category"].value_counts().to_dict()
        if ret_actions is not None and len(ret_actions) > 0 and "offer_category" in ret_actions.columns:
            ret_cats = ret_actions["offer_category"].value_counts().to_dict()

        all_cats = sorted(set(list(act_cats.keys()) + list(ret_cats.keys())))
        rows = []
        for cat in all_cats:
            a = act_cats.get(cat, 0)
            r = ret_cats.get(cat, 0)
            rows.append([cat, _fmt_int(a), _fmt_int(r), _fmt_int(a + r)])
        if rows:
            portfolio_html = (
                "<h3>Offer Category Distribution</h3>"
                + _html_table(
                    ["Category", "Activation Customers", "Retention Customers", "Total"],
                    rows,
                )
            )
        else:
            portfolio_html = "<p><em>No offer portfolio data available.</em></p>"

    vp_callout = _callout(
        "<strong>VP note:</strong> ROI figures are model-estimated using assumed response rates. "
        "Do NOT present to CFO as guaranteed returns. Actual ROI measured via holdout comparison only."
    )

    return (
        f'<section id="s6">'
        f'<h2>Offer Portfolio</h2>'
        f'{portfolio_html}'
        f'{vp_callout}'
        f'</section>'
    )


def _section_channel_distribution(d: dict) -> str:
    act_actions = d["act_actions"]
    ret_actions = d["ret_actions"]

    act_ch: dict = {}
    ret_ch: dict = {}

    if act_actions is not None and len(act_actions) > 0 and "primary_channel" in act_actions.columns:
        act_ch = act_actions["primary_channel"].value_counts().to_dict()
    if ret_actions is not None and len(ret_actions) > 0 and "primary_channel" in ret_actions.columns:
        ret_ch = ret_actions["primary_channel"].value_counts().to_dict()

    all_channels = sorted(set(list(act_ch.keys()) + list(ret_ch.keys())))
    total_all = sum(act_ch.values()) + sum(ret_ch.values())

    rows = []
    for ch in all_channels:
        a = act_ch.get(ch, 0)
        r = ret_ch.get(ch, 0)
        t = a + r
        pct = f"{t / max(total_all, 1) * 100:.1f}%"
        rows.append([ch, _fmt_int(a), _fmt_int(r), _fmt_int(t), pct])

    if rows:
        table_html = _html_table(
            ["Channel", "Activation", "Retention", "Total", "% of All"],
            rows,
        )
    else:
        table_html = "<p><em>No channel data available.</em></p>"

    compliance_note = _callout(
        "<strong>Compliance note:</strong> SMS and push notification volumes must be validated against "
        "channel capacity limits and opt-out suppression lists before deployment. "
        "Email send times must comply with CAN-SPAM / GDPR requirements."
    )

    return (
        f'<section id="s7">'
        f'<h2>Channel Distribution</h2>'
        f'{table_html}'
        f'{compliance_note}'
        f'</section>'
    )


def _section_compliance_fairness(d: dict) -> str:
    fairness_report  = d["fairness_report"]
    stability_report = d["stability_report"]

    # Fairness status
    status = fairness_report.get("status", "unknown")
    if status == "pass" or status == "ok":
        fair_badge = _badge("PASS", "green")
        fair_alert = ""
    elif status == "violation":
        fair_badge = _badge("VIOLATION", "red")
        fair_alert = _callout(
            "<strong>Action required:</strong> Campaign must be paused pending legal/compliance review. "
            "Disparity violation detected under the 80% (four-fifths) adverse-action rule.",
            red=True,
        )
    else:
        fair_badge = _badge(status.upper(), "amber")
        fair_alert = ""

    fairness_html = f"<p><strong>Fairness Status:</strong> {fair_badge}</p>{fair_alert}"

    # Disparity ratios table
    disparity = fairness_report.get("disparity_ratios", {})
    adverse   = fairness_report.get("group_adverse_action_rates", {})
    violations_dict = fairness_report.get("violations", {})
    if disparity:
        disp_rows = []
        for group, ratio in disparity.items():
            adv_rate = adverse.get(group, "N/A")
            adv_str  = _fmt_float(adv_rate) if adv_rate != "N/A" else "N/A"
            ratio_str = _fmt_float(ratio)
            is_violation = group in violations_dict
            status_cell = _badge("Violation", "red") if is_violation else _badge("OK", "green")
            disp_rows.append([group, adv_str, ratio_str, status_cell])
        fairness_html += _html_table(
            ["Group", "Adverse Action Rate", "Disparity Ratio", "Status"],
            disp_rows,
        )

    # PSI / stability section
    feature_psi   = stability_report.get("feature_psi", {})
    alert_features = stability_report.get("alert_features", [])
    n_checked      = stability_report.get("n_features_checked", 0)

    psi_html = ""
    if feature_psi:
        n_ok      = sum(1 for v in feature_psi.values() if v.get("status") == "ok")
        n_monitor = sum(1 for v in feature_psi.values() if v.get("status") == "monitor")
        n_alert   = sum(1 for v in feature_psi.values() if v.get("status") == "alert")
        psi_html = (
            f"<h3>PSI Stability Monitoring</h3>"
            f"<p>Features checked: <strong>{_fmt_int(n_checked)}</strong> — "
            f"OK: {_badge(str(n_ok), 'green')} &nbsp; "
            f"Monitor: {_badge(str(n_monitor), 'amber')} &nbsp; "
            f"Alert: {_badge(str(n_alert), 'red')}</p>"
        )
        if alert_features:
            psi_html += (
                _callout(
                    "<strong>PSI Alert Features (PSI &gt; threshold):</strong> "
                    + ", ".join(f"<code>{f}</code>" for f in alert_features),
                    red=True,
                )
            )
    elif stability_report:
        psi_html = "<h3>PSI Stability Monitoring</h3><p><em>No feature PSI data available.</em></p>"

    return (
        f'<section id="s8">'
        f'<h2>Compliance &amp; Fairness</h2>'
        f'{fairness_html}'
        f'{psi_html}'
        f'</section>'
    )


def _section_action_items(d: dict) -> str:
    act_actions      = d["act_actions"]
    ret_actions      = d["ret_actions"]
    stability_report = d["stability_report"]
    fairness_report  = d["fairness_report"]
    val_report       = d["val_report"]

    def _risk_count(df, band):
        if df is None or len(df) == 0 or "risk_band" not in df.columns:
            return 0
        return int((df["risk_band"] == band).sum())

    act_hr = _risk_count(act_actions, "high_risk")
    ret_hr = _risk_count(ret_actions, "high_risk")
    ret_mr = _risk_count(ret_actions, "medium_risk")

    # Premium high-risk for RM escalation
    prem_hr = 0
    if act_actions is not None and len(act_actions) > 0:
        cols_ok = "customer_segment" in act_actions.columns and "risk_band" in act_actions.columns
        if cols_ok:
            prem_hr = int(
                ((act_actions["customer_segment"] == "premium") &
                 (act_actions["risk_band"] == "high_risk")).sum()
            )

    # Recurring txn gap (activation)
    recurring_note = ""
    if act_actions is not None and len(act_actions) > 0 and "has_recurring_txn" in act_actions.columns:
        n_no_recurring = int((act_actions["has_recurring_txn"] == False).sum() +
                             (act_actions["has_recurring_txn"] == 0).sum())
        if len(act_actions) > 0:
            pct_no_rec = n_no_recurring / len(act_actions) * 100
            recurring_note = (
                f"Recurring Txn Setup Push: {_fmt_float(pct_no_rec, 1)}% of activation customers "
                f"({_fmt_int(n_no_recurring)}) have no recurring transaction — push in-app setup wizard."
            )

    # PSI / stability summary
    alert_features    = stability_report.get("alert_features", [])
    retrain_rec       = stability_report.get("retraining_recommended", False)
    val_retrain       = val_report.get("retraining_recommended", False)
    retrain_flag      = retrain_rec or val_retrain
    fairness_status   = fairness_report.get("status", "unknown")

    def _action_box(title: str, items: list) -> str:
        li_items = "".join(f"<li>{item}</li>" for item in items)
        return (
            f'<div class="action-box">'
            f'<h4>{title}</h4>'
            f'<ul style="margin:0;padding-left:20px;">{li_items}</ul>'
            f'</div>'
        )

    launch_items = [
        f"<strong>Activation Wave 1 (High-Risk):</strong> {_fmt_int(act_hr)} customers — "
        f"load <code>activation_action_list</code> into CRM; budget TBD by marketing.",
        f"<strong>RM Escalation:</strong> {_fmt_int(prem_hr)} premium high-risk customers — "
        "assign dedicated Relationship Manager outreach within 48 hours.",
    ]

    within_30_items = [
        f"<strong>Retention Wave 1:</strong> {_fmt_int(ret_hr + ret_mr)} medium+high risk retention "
        f"customers — load <code>retention_action_list</code> into CRM.",
        "<strong>A/B Holdout Check:</strong> Confirm 20% holdout control group is suppressed "
        "from all campaign sends. Outcome data collection starts at go-live.",
        recurring_note if recurring_note else
        "<strong>Recurring Txn Setup Push:</strong> Review activation cohort for customers "
        "without recurring transaction — consider in-app setup wizard prompt.",
    ]

    governance_items = [
        f"<strong>PSI Status:</strong> "
        + (f"{len(alert_features)} features in alert state: {', '.join(alert_features[:5])}"
           if alert_features else "All features within normal PSI range."),
        f"<strong>Fairness Status:</strong> {fairness_status.upper()} — "
        + ("Review complete before launch." if fairness_status == "violation"
           else "No violations detected."),
        f"<strong>Retraining Recommendation:</strong> "
        + ("Retraining triggered by PSI alerts and/or power analysis. Schedule within 2 weeks."
           if retrain_flag else "No retraining required at this time. Review again next month."),
    ]

    return (
        f'<section id="s9">'
        f'<h2>Consolidated Action Items</h2>'
        + _action_box("LAUNCH THIS WEEK", launch_items)
        + _action_box("WITHIN 30 DAYS", within_30_items)
        + _action_box("MODEL GOVERNANCE (DATA TEAM)", governance_items)
        + '</section>'
    )


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def _build_nav() -> str:
    links = "".join(f'<a href="#{anchor}">{label}</a>' for anchor, label in _NAV_LINKS)
    return f'<nav><div style="max-width:1200px;margin:0 auto;">{links}</div></nav>'


def _build_html(sections: list, run_date: str) -> str:
    nav      = _build_nav()
    body     = "\n".join(sections)
    ts       = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    footer   = (
        f'<footer style="text-align:center;padding:24px;font-size:12px;color:var(--grey-dark);">'
        f'Generated {ts} &nbsp;|&nbsp; <strong>Confidential — Internal Use Only</strong>'
        f'</footer>'
    )
    return (
        '<!DOCTYPE html><html lang="en">'
        '<head>'
        f'<meta charset="UTF-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>Banking Pipeline Report — {run_date}</title>'
        f'<style>{_CSS}</style>'
        '</head>'
        '<body>'
        f'{nav}'
        f'<div class="container">{body}{footer}</div>'
        '</body>'
        '</html>'
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_business_report(output_dir: str, date_str: str) -> str:
    """
    Read step output files from output_dir, generate HTML report.
    Returns path to the written HTML file.
    """
    d = _load_all(output_dir, date_str)

    run_date = date_str

    sections = [
        _section_executive_summary(d, run_date),
        _section_model_accuracy(d),
        _section_audience(d),
        _section_sample_customers(d),
        _section_campaign_briefs(d),
        _section_offer_portfolio(d),
        _section_channel_distribution(d),
        _section_compliance_fairness(d),
        _section_action_items(d),
    ]

    html = _build_html(sections, run_date)

    out_path = os.path.join(output_dir, f"business_report_{date_str}.html")
    os.makedirs(output_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return out_path
