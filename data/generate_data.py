"""Synthetic banking card transaction data generator."""
import numpy as np
import pandas as pd
import yaml
import os
import uuid
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

MCC_MERCHANT_POOLS = {
    5411: ["Walmart Grocery", "Kroger", "Safeway", "Publix", "Albertsons"],
    5412: ["Whole Foods", "Trader Joes", "Sprouts", "Natural Grocers"],
    5422: ["Costco", "Sams Club", "BJs Wholesale"],
    5441: ["7-Eleven", "Circle K", "Wawa"],
    5451: ["Aldi", "Lidl", "Fresh Market"],
    5812: ["McDonalds", "Subway", "Chipotle", "Panera Bread", "Chick-fil-A"],
    5814: ["Starbucks", "Dunkin", "Peets Coffee"],
    5813: ["Local Bar", "Applebees", "TGI Fridays"],
    4511: ["Delta Airlines", "United Airlines", "American Airlines", "Southwest"],
    4111: ["Amtrak", "Metro Transit", "Uber", "Lyft"],
    4121: ["Hertz", "Enterprise", "Avis", "National Car Rental"],
    3000: ["Marriott Hotels", "Hilton", "Hyatt", "IHG"],
    3500: ["Holiday Inn", "Best Western", "Hampton Inn"],
    5541: ["Shell", "BP", "Chevron", "ExxonMobil", "Sunoco"],
    5542: ["Murphy USA", "QuickTrip", "Wawa Gas"],
    5172: ["Speedway", "Pilot Flying J"],
    4899: ["Netflix", "Hulu", "Disney+", "HBO Max"],
    5968: ["Amazon Prime", "Spotify", "Apple Music"],
    7372: ["Adobe Creative Cloud", "Microsoft 365", "Dropbox"],
    4900: ["ConEd", "Pacific Gas", "Duke Energy", "Dominion"],
    4911: ["Georgia Power", "ComEd", "Entergy"],
    4924: ["National Gas", "Southern Company Gas"],
    5600: ["Gap", "Old Navy", "H&M", "Zara"],
    5621: ["Womens Boutique", "Ann Taylor", "White House Black Market"],
    5651: ["JCPenney", "Kohls", "Macys"],
    5661: ["Nike", "Foot Locker", "DSW"],
    5311: ["Target", "Walmart", "Kmart"],
    5331: ["Dollar Tree", "Dollar General", "Five Below"],
    7832: ["AMC Theaters", "Regal Cinemas", "Cinemark"],
    7922: ["Ticketmaster", "StubHub", "Eventbrite"],
    7996: ["Six Flags", "Universal Studios", "Disney World"],
    7993: ["DraftKings", "FanDuel"],
    7941: ["NFL Shop", "NBA Store", "Sports Authority"],
}

MCC_AMOUNT_PARAMS = {
    5411: (55, 0.5), 5412: (70, 0.5), 5422: (120, 0.4),
    5441: (15, 0.6), 5451: (45, 0.5),
    5812: (18, 0.7), 5814: (7, 0.6), 5813: (35, 0.7),
    4511: (350, 0.6), 4111: (22, 0.8), 4121: (80, 0.5),
    3000: (180, 0.5), 3500: (110, 0.5),
    5541: (55, 0.4), 5542: (50, 0.4), 5172: (60, 0.4),
    4899: (15, 0.2), 5968: (12, 0.2), 7372: (20, 0.3),
    4900: (95, 0.4), 4911: (85, 0.4), 4924: (70, 0.4),
    5600: (65, 0.6), 5621: (80, 0.6), 5651: (90, 0.5),
    5661: (75, 0.5), 5311: (55, 0.5), 5331: (20, 0.5),
    7832: (25, 0.4), 7922: (95, 0.6), 7996: (85, 0.5),
    7993: (50, 0.8), 7941: (45, 0.5),
}

SEGMENT_MCC_PROBS = {
    "premium": {
        5812: 0.12, 5411: 0.08, 4511: 0.10, 3000: 0.08, 5600: 0.08,
        5814: 0.07, 5541: 0.05, 7832: 0.05, 4899: 0.06, 5651: 0.06,
        4111: 0.05, 5422: 0.06, 5812: 0.09, 4900: 0.05, 7922: 0.04,
    },
    "standard": {
        5411: 0.18, 5812: 0.15, 5541: 0.10, 5814: 0.08, 5311: 0.08,
        4111: 0.07, 4899: 0.06, 5651: 0.05, 7832: 0.05, 4900: 0.06,
        5331: 0.04, 5441: 0.04, 4121: 0.04,
    },
    "student": {
        5814: 0.20, 5812: 0.18, 5411: 0.10, 4111: 0.12, 4899: 0.10,
        5968: 0.08, 7832: 0.07, 5331: 0.06, 5441: 0.05, 5541: 0.04,
    },
}

SEASONALITY = {
    1: 0.80, 2: 0.85, 3: 0.90, 4: 0.95, 5: 1.00,
    6: 1.05, 7: 1.10, 8: 1.05, 9: 0.95, 10: 1.00,
    11: 1.10, 12: 1.30,
}

CHANNEL_HOUR_PEAKS = {
    "mobile_app": (19, 3),
    "web": (13, 4),
    "POS": (12, 3),
    "ATM": (12, 2),
}


def _get_segment_mccs(segment: str) -> tuple:
    probs_dict = SEGMENT_MCC_PROBS[segment]
    mccs = list(probs_dict.keys())
    probs = list(probs_dict.values())
    total = sum(probs)
    probs = [p / total for p in probs]
    return mccs, probs


def _sample_amount(mcc: int, rng: np.random.Generator) -> float:
    mu, sigma = MCC_AMOUNT_PARAMS.get(mcc, (40, 0.6))
    amount = rng.lognormal(np.log(mu), sigma)
    return max(1.01, round(amount, 2))


def _apply_seasonality(date: datetime, base: float) -> float:
    return base * SEASONALITY.get(date.month, 1.0)


def _sample_transaction_time(date: datetime, channel: str, rng: np.random.Generator) -> datetime:
    peak_hour, std_hours = CHANNEL_HOUR_PEAKS.get(channel, (12, 3))
    hour = int(np.clip(rng.normal(peak_hour, std_hours), 0, 23))
    minute = rng.integers(0, 60)
    return date.replace(hour=hour, minute=minute, second=0)


def _get_merchant(mcc: int, rng: np.random.Generator) -> str:
    pool = MCC_MERCHANT_POOLS.get(mcc, [f"Merchant_{mcc}"])
    return rng.choice(pool)


def _generate_customers(n: int, date_start: datetime, date_end: datetime, rng: np.random.Generator) -> pd.DataFrame:
    segments = rng.choice(["premium", "standard", "student"], size=n, p=[0.15, 0.70, 0.15])
    ages = []
    for seg in segments:
        if seg == "premium":
            ages.append(int(np.clip(rng.normal(47, 10), 35, 70)))
        elif seg == "standard":
            ages.append(int(np.clip(rng.normal(38, 10), 25, 65)))
        else:
            ages.append(int(np.clip(rng.normal(22, 3), 18, 28)))

    total_days = (date_end - date_start).days
    # Recency-weighted card issue dates: more new cards recently
    weights = np.linspace(0.5, 1.5, total_days)
    weights /= weights.sum()
    issue_offsets = rng.choice(total_days, size=n, p=weights)
    card_issue_dates = [date_start + timedelta(days=int(d)) for d in issue_offsets]

    archetype_probs = [0.08, 0.07, 0.45, 0.15, 0.10, 0.15]
    archetypes = rng.choice(
        ["never_activated", "slow_activator", "healthy_active", "declining_active", "high_value", "churned"],
        size=n, p=archetype_probs,
    )

    customer_ids = [f"C{str(i).zfill(6)}" for i in range(n)]
    card_ids = [f"K{str(i).zfill(6)}" for i in range(n)]

    # Assign recurring merchant per customer (for has_recurring_txn detection)
    recurring_mccs = [4900, 4911, 4924, 4899, 5968]
    has_recurring = rng.random(n) < 0.45
    recurring_mcc = rng.choice(recurring_mccs, size=n)
    recurring_merchant = [_get_merchant(m, rng) for m in recurring_mcc]

    return pd.DataFrame({
        "customer_id": customer_ids,
        "card_id": card_ids,
        "customer_age": ages,
        "customer_segment": segments,
        "card_issue_date": card_issue_dates,
        "archetype": archetypes,
        "has_recurring_setup": has_recurring,
        "recurring_mcc": recurring_mcc,
        "recurring_merchant": recurring_merchant,
        "consent_sms": rng.random(n) > 0.20,
        "consent_email": rng.random(n) > 0.05,
        "consent_push": rng.random(n) > 0.25,
    })


def _apply_quiet_periods(txn_days: list, total_days: int, rng: np.random.Generator) -> list:
    """Randomly remove transactions from 1–2 quiet stretches (holiday, illness, travel)."""
    n_quiet = rng.integers(0, 3)
    for _ in range(n_quiet):
        quiet_start = rng.integers(0, max(1, total_days - 20))
        quiet_len = rng.integers(10, 40)
        txn_days = [d for d in txn_days if not (quiet_start <= d < quiet_start + quiet_len)]
    return txn_days


def _apply_burst_period(txn_days: list, total_days: int, rng: np.random.Generator) -> list:
    """Add a short spending spike (holiday shopping, trip, etc.)."""
    if total_days < 14:
        return txn_days
    burst_start = rng.integers(0, max(1, total_days - 14))
    n_extra = rng.integers(2, 6)
    extra = rng.integers(burst_start, min(total_days, burst_start + 14), size=n_extra).tolist()
    return sorted(txn_days + extra)


def _drop_fraction(txn_days: list, drop_rate: float, rng: np.random.Generator) -> list:
    """Randomly drop a fraction of transactions to add per-event noise."""
    if not txn_days:
        return txn_days
    mask = rng.random(len(txn_days)) > drop_rate
    return [d for d, keep in zip(txn_days, mask) if keep]


def _generate_transactions_for_customer(
    customer: pd.Series,
    date_end: datetime,
    rng: np.random.Generator,
) -> list:
    txns = []
    archetype = customer["archetype"]
    segment = customer["customer_segment"]
    issue_date = customer["card_issue_date"]
    cid = customer["customer_id"]
    kid = customer["card_id"]
    has_recurring = customer["has_recurring_setup"]
    rec_mcc = customer["recurring_mcc"]
    rec_merchant = customer["recurring_merchant"]

    mccs, mcc_probs = _get_segment_mccs(segment)
    channels = ["mobile_app", "web", "POS", "ATM"]

    if segment == "premium":
        channel_probs = [0.35, 0.20, 0.40, 0.05]
    elif segment == "student":
        channel_probs = [0.50, 0.20, 0.25, 0.05]
    else:
        channel_probs = [0.30, 0.15, 0.45, 0.10]

    # Per-customer channel noise: shift probs slightly so no two customers are identical
    channel_noise = rng.dirichlet(np.array(channel_probs) * 8)
    channel_probs = channel_noise.tolist()

    total_days = max(1, (date_end - issue_date).days)

    # ── Archetype blending (15% chance): borrow behavior from a neighbor archetype
    effective_archetype = archetype
    if rng.random() < 0.15:
        blend_map = {
            "never_activated": "slow_activator",
            "slow_activator": "never_activated",
            "healthy_active": "declining_active",
            "declining_active": "healthy_active",
            "high_value": "healthy_active",
            "churned": "declining_active",
        }
        effective_archetype = blend_map.get(archetype, archetype)

    if effective_archetype == "never_activated":
        # Wider range: 0–4 transactions so borderline cases exist near threshold
        n_txns_total = rng.integers(0, 5)
        if n_txns_total > 0 and total_days > 1:
            txn_days = sorted(rng.integers(0, total_days, size=n_txns_total).tolist())
        else:
            txn_days = []
        monthly_rate = 0

    elif effective_archetype == "slow_activator":
        # 0–3 in first 45 days, 2–10 after — overlap with never_activated at low end
        days_avail = total_days
        first_phase = min(45, days_avail)
        second_phase = max(0, min(days_avail, 90) - first_phase)
        n_early = rng.integers(0, 4)
        n_late = rng.integers(2, 11)
        early = sorted(rng.integers(0, max(1, first_phase), size=n_early).tolist()) if n_early > 0 else []
        if second_phase > 1:
            late = sorted(rng.integers(first_phase, max(first_phase + 1, first_phase + second_phase), size=n_late).tolist())
        else:
            late = []
        txn_days = early + late
        monthly_rate = rng.integers(3, 10)
        # 20% of slow activators never fully ramp — look like never_activated beyond 90d
        if rng.random() < 0.20:
            txn_days = [d for d in txn_days if d < 90]

    elif effective_archetype == "healthy_active":
        # Wider monthly rate range + random startup delay (some healthy users start slowly)
        monthly_rate = int(np.clip(rng.normal(10, 4), 3, 22))
        startup_delay = int(rng.exponential(5))  # some customers take days to start
        n_txns_total = max(0, int(monthly_rate * total_days / 30))
        if n_txns_total > 0 and total_days > 1:
            txn_days = sorted((rng.integers(startup_delay, max(startup_delay + 1, total_days), size=n_txns_total)).tolist())
        else:
            txn_days = []
        # 15% chance of a 30–60 day hibernation mid-history (vacation, card stolen/replaced)
        if rng.random() < 0.15 and total_days > 120:
            gap_start = rng.integers(30, max(31, total_days - 90))
            gap_len = rng.integers(30, 61)
            txn_days = [d for d in txn_days if not (gap_start <= d < gap_start + gap_len)]
            # Resume after gap at original rate
            resume_n = max(0, int(monthly_rate * (total_days - gap_start - gap_len) / 30))
            if resume_n > 0 and gap_start + gap_len < total_days:
                extra = rng.integers(gap_start + gap_len, total_days, size=resume_n).tolist()
                txn_days = sorted(txn_days + extra)

    elif effective_archetype == "declining_active":
        # Gaussian noise on decay rate; 30% of decliners actually stabilize
        monthly_rate = int(np.clip(rng.normal(9, 3), 3, 18))
        txn_days = []
        day = 0
        decay_rate = rng.uniform(0.01, 0.04)  # randomize decay speed
        stabilizes = rng.random() < 0.30
        stable_floor = rng.integers(2, 6) if stabilizes else 0
        current_rate = monthly_rate
        while day < total_days:
            current_rate = max(stable_floor, current_rate * (1 - decay_rate))
            gap = max(1, int(30 / max(0.1, current_rate) * rng.exponential(1)))
            day += gap
            if day < total_days:
                txn_days.append(day)

    elif effective_archetype == "high_value":
        monthly_rate = int(np.clip(rng.normal(28, 8), 12, 50))
        n_txns_total = max(0, int(monthly_rate * total_days / 30))
        txn_days = sorted(rng.integers(0, max(1, total_days), size=n_txns_total).tolist())

    else:  # churned
        active_days = rng.integers(60, 300)
        active_days = min(active_days, total_days - 30)
        if active_days <= 0:
            return txns
        monthly_rate = int(np.clip(rng.normal(7, 3), 2, 15))
        n_txns_total = max(0, int(monthly_rate * active_days / 30))
        txn_days = sorted(rng.integers(0, max(1, active_days), size=n_txns_total).tolist())
        # 20% of churned customers make 1–3 zombie transactions after their active period
        if rng.random() < 0.20 and active_days < total_days - 10:
            zombie_n = rng.integers(1, 4)
            zombie_days = rng.integers(active_days, total_days, size=zombie_n).tolist()
            txn_days = sorted(txn_days + zombie_days)

    # ── Behavioral noise layer (applied to all archetypes) ────────────────
    # 1. Random quiet periods (skip transactions during a stretch)
    if total_days > 60 and rng.random() < 0.40:
        txn_days = _apply_quiet_periods(txn_days, total_days, rng)
    # 2. Random spending burst (holiday, trip, one-off)
    if rng.random() < 0.25:
        txn_days = _apply_burst_period(txn_days, total_days, rng)
    # 3. Per-transaction random drop (card left at home, declined, forgotten)
    drop_rate = rng.uniform(0.05, 0.20)
    txn_days = _drop_fraction(txn_days, drop_rate, rng)

    for day_offset in txn_days:
        txn_date = issue_date + timedelta(days=int(day_offset))
        if txn_date > date_end:
            break
        mcc = int(rng.choice(mccs, p=mcc_probs))
        channel = rng.choice(channels, p=channel_probs)
        base_amount = _sample_amount(mcc, rng)
        amount = round(_apply_seasonality(txn_date, base_amount), 2)
        txn_time = _sample_transaction_time(txn_date, channel, rng)
        merchant = _get_merchant(mcc, rng)
        txns.append({
            "transaction_id": str(uuid.uuid4()),
            "customer_id": cid,
            "card_id": kid,
            "transaction_date": txn_time,
            "transaction_amount": amount,
            "transaction_type": "purchase",
            "merchant_category_code": mcc,
            "merchant_name": merchant,
            "channel": channel,
        })

    # Add recurring transactions (fixed merchant, fixed amount monthly)
    if has_recurring and archetype not in ["never_activated"]:
        total_days = (date_end - issue_date).days
        rec_amount = round(rng.uniform(30, 150), 2)
        month = 0
        while month * 30 < total_days:
            pay_day = min(month * 30 + rng.integers(1, 5), total_days - 1)
            txn_date = issue_date + timedelta(days=int(pay_day))
            if txn_date > date_end:
                break
            if archetype == "churned" and pay_day > total_days - 60:
                break
            txns.append({
                "transaction_id": str(uuid.uuid4()),
                "customer_id": cid,
                "card_id": kid,
                "transaction_date": txn_date.replace(hour=9, minute=0),
                "transaction_amount": rec_amount,
                "transaction_type": "recurring",
                "merchant_category_code": int(rec_mcc),
                "merchant_name": rec_merchant,
                "channel": "web",
            })
            month += 1

    # Inject occasional refunds (~5% of purchase count)
    n_refunds = int(len(txns) * 0.05)
    if n_refunds > 0 and len(txns) > 0:
        for _ in range(n_refunds):
            orig = txns[rng.integers(0, len(txns))]
            refund_date = orig["transaction_date"] + timedelta(days=int(rng.integers(1, 5)))
            if refund_date <= date_end:
                txns.append({
                    "transaction_id": str(uuid.uuid4()),
                    "customer_id": cid,
                    "card_id": kid,
                    "transaction_date": refund_date,
                    "transaction_amount": orig["transaction_amount"],
                    "transaction_type": "refund",
                    "merchant_category_code": orig["merchant_category_code"],
                    "merchant_name": orig["merchant_name"],
                    "channel": orig["channel"],
                })

    return txns


def generate(config_path: str = "config.yaml", output_dir: str = None) -> tuple:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    dcfg = cfg["data"]
    rng = np.random.default_rng(dcfg["random_seed"])
    date_start = datetime.strptime(dcfg["date_start"], "%Y-%m-%d")
    date_end = datetime.strptime(dcfg["date_end"], "%Y-%m-%d")
    n_customers = dcfg["n_customers"]
    out_dir = output_dir or dcfg["raw_dir"]
    os.makedirs(out_dir, exist_ok=True)

    print(f"Generating {n_customers:,} customers...")
    customers_df = _generate_customers(n_customers, date_start, date_end, rng)

    print("Generating transactions...")
    all_txns = []
    for i, (_, customer) in enumerate(customers_df.iterrows()):
        txns = _generate_transactions_for_customer(customer, date_end, rng)
        all_txns.extend(txns)
        if (i + 1) % 5000 == 0:
            print(f"  Processed {i+1:,}/{n_customers:,} customers, {len(all_txns):,} transactions so far")

    txn_df = pd.DataFrame(all_txns)
    txn_df["transaction_date"] = pd.to_datetime(txn_df["transaction_date"])
    txn_df = txn_df.sort_values(["customer_id", "transaction_date"]).reset_index(drop=True)

    customers_path = os.path.join(out_dir, "customers.parquet")
    txn_path = os.path.join(out_dir, "transactions.parquet")
    customers_df.to_parquet(customers_path, index=False)
    txn_df.to_parquet(txn_path, index=False)

    print(f"Done. {len(customers_df):,} customers, {len(txn_df):,} transactions")
    print(f"Saved to {customers_path} and {txn_path}")
    return customers_df, txn_df


if __name__ == "__main__":
    generate()
