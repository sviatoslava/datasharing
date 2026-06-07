"""A/B test power analysis: compute required sample sizes and holdout fractions."""
import numpy as np
from scipy import stats


def compute_required_sample_size(
    baseline_rate: float,
    min_detectable_effect: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict:
    """Two-proportion z-test power calculation."""
    p1 = baseline_rate
    p2 = baseline_rate + min_detectable_effect
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    p_bar = (p1 + p2) / 2
    n = (z_alpha * np.sqrt(2 * p_bar * (1 - p_bar)) + z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    n = int(np.ceil(n / (min_detectable_effect ** 2)))
    n_control = max(1, int(n))
    n_treatment = n_control * 4  # 80/20 split: 4:1 treatment:control
    total = n_control + n_treatment
    holdout_fraction = round(n_control / total, 3)

    return {
        "n_control": n_control,
        "n_treatment": n_treatment,
        "total_required": total,
        "holdout_fraction": holdout_fraction,
        "baseline_rate": baseline_rate,
        "min_detectable_effect": min_detectable_effect,
        "alpha": alpha,
        "power": power,
    }


def check_sufficient_power(
    n_available: int,
    baseline_rate: float,
    min_detectable_effect: float,
    holdout_fraction: float = 0.20,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict:
    required = compute_required_sample_size(baseline_rate, min_detectable_effect, alpha, power)
    n_control = int(n_available * holdout_fraction)
    n_treatment = n_available - n_control
    is_sufficient = n_available >= required["total_required"]
    waves_needed = int(np.ceil(required["total_required"] / max(1, n_available)))
    return {
        "n_available": n_available,
        "n_control": n_control,
        "n_treatment": n_treatment,
        "required_total": required["total_required"],
        "required_holdout_fraction": required["holdout_fraction"],
        "is_sufficient": is_sufficient,
        "waves_needed_if_insufficient": waves_needed if not is_sufficient else 1,
        "recommendation": "Sufficient for 1-wave test" if is_sufficient
            else f"Pool {waves_needed} campaign waves for adequate power",
    }
