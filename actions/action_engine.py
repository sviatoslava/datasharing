"""Trigger-to-action mapping engine combining ML scores, SHAP triggers, and config rules."""
import pandas as pd
import numpy as np
from datetime import datetime


def assign_risk_band(prob: float, model_type: str, config: dict) -> str:
    if model_type == "activation":
        if prob < 0.35:
            return "high_risk"
        elif prob < 0.65:
            return "medium_risk"
        else:
            return "low_risk"
    else:  # retention
        if prob >= 0.70:
            return "high_risk"
        elif prob >= 0.40:
            return "medium_risk"
        else:
            return "low_risk"


def compute_priority_score(
    ml_prob: float,
    customer_segment: str,
    model_type: str,
    days_since_last_txn: int,
    config: dict,
) -> float:
    pw = config["actions"]["priority_weights"]
    ltv_weight = pw["ltv"].get(customer_segment, 1.0)
    urgency_threshold = pw.get("urgency_bonus_days_threshold", 45)
    urgency_bonus = pw.get("urgency_bonus_value", 0.30)
    urgency = urgency_bonus if (model_type == "retention" and days_since_last_txn > urgency_threshold) else 0.0
    return round(ml_prob * ltv_weight * (1 + urgency), 4)


def _select_channel(
    preferred_channel: str,
    digital_adoption: float,
    primary_template: dict,
) -> str:
    low_digital = digital_adoption < 0.2 or preferred_channel in ["POS", "ATM"]
    if "channel_digital" in primary_template and "channel_nondigital" in primary_template:
        return primary_template["channel_nondigital"] if low_digital else primary_template["channel_digital"]
    return primary_template.get("channel", "email")


def _apply_trigger_overrides(
    actions: list,
    triggers: list,
    customer_segment: str,
    preferred_channel: str,
    digital_adoption: float,
    days_since_last_txn: int,
    model_type: str,
    has_recurring_txn: bool,
) -> list:
    """Apply rule-based modifications to base action sequences."""
    modified = []
    for action in actions:
        action = dict(action)

        # Channel routing override
        if digital_adoption < 0.2 or preferred_channel in ["POS", "ATM"]:
            if action.get("channel_digital") == "push_notification":
                action["resolved_channel"] = action.get("channel_nondigital", "sms")
            else:
                action["resolved_channel"] = action.get("channel", "email")
        else:
            action["resolved_channel"] = action.get("channel_digital", action.get("channel", "email"))

        # Offer escalation: strong velocity drop
        for trig in triggers:
            feat = trig.get("trigger", "")
            direction = trig.get("direction", "")
            magnitude = abs(trig.get("shap", 0))
            if "velocity_change" in feat and direction == "low" and magnitude > 0.5:
                offer_pct = action.get("offer_value_standard", 0)
                if isinstance(offer_pct, float) and offer_pct < 1:
                    action["offer_escalated"] = True
                    action["offer_escalation_pct"] = 0.05

        # Premium segment: add RM alert
        if customer_segment == "premium" and model_type == "retention":
            action["add_rm_alert"] = True

        # Recurring tutorial for non-recurring activation customers
        if model_type == "activation" and not has_recurring_txn:
            action["add_recurring_tutorial"] = True

        # Near-churn urgency hook
        if model_type == "retention" and days_since_last_txn > 45:
            action["add_urgency_hook"] = True
            action["urgency_hook_type"] = "statement_credit"

        modified.append(action)

    return modified


def assign_actions(
    scores_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    model_type: str,
    config: dict,
    run_date: str = None,
) -> pd.DataFrame:
    """
    Assign action sequences to all scored customers.

    scores_df must have: customer_id, ml_probability, customer_segment,
                         preferred_channel, digital_adoption (or digital_adoption_30d),
                         days_since_last_txn (retention) or days_since_card_issue (activation)
    shap_df must have: customer_id, trigger_1..N, trigger_1..N_direction, trigger_1..N_shap
    """
    action_cfg = config["actions"][model_type]
    run_date = run_date or datetime.now().strftime("%Y-%m-%d")

    # Merge SHAP triggers into scores
    merged = scores_df.merge(shap_df, on="customer_id", how="left")

    rows = []
    for _, row in merged.iterrows():
        cid = row["customer_id"]
        prob = float(row["ml_probability"])
        segment = row.get("customer_segment", "standard")
        preferred_ch = row.get("preferred_channel", "email")
        digital_adop = float(row.get("digital_adoption", row.get("digital_adoption_30d", 0.3)))
        days_since = int(row.get("days_since_last_txn", row.get("days_since_card_issue", 0)))
        has_recurring = bool(row.get("has_recurring_txn", 0))

        risk_band = assign_risk_band(prob, model_type, config)
        priority = compute_priority_score(prob, segment, model_type, days_since, config)

        # Collect SHAP triggers
        triggers = []
        for i in range(1, 4):
            t_key = f"trigger_{i}"
            d_key = f"trigger_{i}_direction"
            s_key = f"trigger_{i}_shap"
            if t_key in row and pd.notna(row[t_key]):
                triggers.append({
                    "trigger": row[t_key],
                    "direction": row.get(d_key, ""),
                    "shap": float(row.get(s_key, 0)),
                })

        # Get base action sequence from config
        base_actions = action_cfg.get(risk_band, [])
        modified_actions = _apply_trigger_overrides(
            base_actions, triggers, segment, preferred_ch, digital_adop,
            days_since, model_type, has_recurring,
        )

        trigger_summary = "; ".join([
            f"{t['trigger']} is {t['direction']}" for t in triggers[:3]
        ]) if triggers else "no triggers"

        # Build action columns (up to 3 actions)
        out_row = {
            "customer_id": cid,
            "model_type": model_type,
            "risk_band": risk_band,
            "ml_probability": round(prob, 4),
            "priority_score": priority,
            "customer_segment": segment,
            "preferred_channel": preferred_ch,
            "trigger_summary": trigger_summary,
            "run_date": run_date,
        }

        for i, action in enumerate(modified_actions[:3], start=1):
            out_row[f"action_{i}_type"] = action.get("type", "")
            out_row[f"action_{i}_channel"] = action.get("resolved_channel", action.get("channel", "email"))
            out_row[f"action_{i}_offer_type"] = action.get("offer_type", "")
            out_row[f"action_{i}_send_days"] = str(action.get("send_days", [1]))
            out_row[f"action_{i}_duration_days"] = action.get("offer_duration_days", 30)
            out_row[f"action_{i}_frequency_touches"] = action.get("frequency_touches", 1)
            out_row[f"action_{i}_escalated"] = action.get("offer_escalated", False)
            out_row[f"action_{i}_add_rm_alert"] = action.get("add_rm_alert", False)
            out_row[f"action_{i}_add_urgency_hook"] = action.get("add_urgency_hook", False)

        for i in range(1, 4):
            t_key = f"trigger_{i}"
            d_key = f"trigger_{i}_direction"
            out_row[f"top_trigger_{i}"] = row.get(t_key, "")
            out_row[f"top_trigger_{i}_dir"] = row.get(d_key, "")

        rows.append(out_row)

    result = pd.DataFrame(rows).sort_values("priority_score", ascending=False).reset_index(drop=True)
    return result
