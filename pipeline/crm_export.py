"""Channel-specific CRM export files with compliance checks."""
import pandas as pd
import os
from datetime import datetime


COMPLIANCE_DEFAULTS = {
    "sms_requires_express_written_consent": True,
    "email_requires_opt_in": True,
    "max_sms_per_month": 4,
    "quiet_hours_start": "21:00",
    "quiet_hours_end": "08:00",
    "suppression_list_check": True,
}


def _is_quiet_hour(send_hour: int, quiet_start: str, quiet_end: str) -> bool:
    start_h = int(quiet_start.split(":")[0])
    end_h = int(quiet_end.split(":")[0])
    if start_h > end_h:  # crosses midnight
        return send_hour >= start_h or send_hour < end_h
    return end_h > send_hour >= start_h


def export_crm_files(
    schedule_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    config: dict,
    run_date: datetime,
    output_dir: str = "outputs",
) -> dict:
    """
    Split the campaign schedule into channel-specific export files.
    Applies compliance checks (consent, quiet hours, suppression).
    """
    compliance = {**COMPLIANCE_DEFAULTS, **config.get("compliance", {})}
    quiet_start = compliance["quiet_hours_start"]
    quiet_end = compliance["quiet_hours_end"]
    date_str = run_date.strftime("%Y-%m-%d")
    os.makedirs(output_dir, exist_ok=True)

    # Build consent lookup from customers
    consent_map = {}
    if "consent_sms" in customers_df.columns:
        for _, r in customers_df.iterrows():
            consent_map[r["customer_id"]] = {
                "sms": bool(r.get("consent_sms", True)),
                "email": bool(r.get("consent_email", True)),
                "push": bool(r.get("consent_push", True)),
            }

    suppressed = set()  # in production: load from suppression list

    def check_compliance(row, channel: str) -> bool:
        cid = row["customer_id"]
        send_hour = int(row.get("scheduled_hour_utc", 9))

        if cid in suppressed:
            return False
        if _is_quiet_hour(send_hour, quiet_start, quiet_end):
            return False
        if compliance.get("suppression_list_check") and cid in suppressed:
            return False

        consents = consent_map.get(cid, {"sms": True, "email": True, "push": True})
        if channel == "sms" and compliance["sms_requires_express_written_consent"]:
            return consents.get("sms", True)
        if channel == "email" and compliance["email_requires_opt_in"]:
            return consents.get("email", True)
        if channel == "push_notification":
            return consents.get("push", True)
        return True

    channels = {
        "email": [],
        "push_notification": [],
        "sms": [],
        "crm_alert": [],
        "in_app_banner": [],
    }

    n_suppressed = 0
    for _, row in schedule_df.iterrows():
        channel = row.get("channel", "email")
        if channel not in channels:
            channel = "email"
        if check_compliance(row, channel):
            channels[channel].append(dict(row))
        else:
            n_suppressed += 1

    export_paths = {}
    for channel, rows in channels.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        channel_slug = channel.replace("_", "")
        path = os.path.join(output_dir, f"crm_{channel_slug}_{date_str}.csv")
        df.to_csv(path, index=False)
        export_paths[channel] = path
        print(f"  {channel}: {len(df):,} records → {path}")

    print(f"  {n_suppressed} records suppressed (compliance/consent/quiet-hours)")
    return {"export_paths": export_paths, "n_suppressed": n_suppressed}
