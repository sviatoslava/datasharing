"""Thompson Sampling bandit for offer type optimization within campaign buckets."""
import numpy as np
import json
import os


class ThompsonSamplingBandit:
    """
    Beta-Bernoulli Thompson Sampling over offer types per (campaign_bucket, risk_band).
    Prior: Beta(1,1) — uniform, cold-startable.
    """

    def __init__(self, offer_types: list):
        self.offer_types = offer_types
        # alpha = successes + 1, beta = failures + 1
        self.alphas = {ot: 1.0 for ot in offer_types}
        self.betas = {ot: 1.0 for ot in offer_types}

    def sample(self) -> str:
        """Sample from posterior and return the offer type with highest sampled reward."""
        samples = {ot: np.random.beta(self.alphas[ot], self.betas[ot]) for ot in self.offer_types}
        return max(samples, key=samples.get)

    def update(self, offer_type: str, redeemed: bool) -> None:
        if offer_type not in self.alphas:
            return
        if redeemed:
            self.alphas[offer_type] += 1
        else:
            self.betas[offer_type] += 1

    def get_state(self) -> dict:
        return {"alphas": dict(self.alphas), "betas": dict(self.betas)}

    def load_state(self, state: dict) -> None:
        self.alphas = state.get("alphas", self.alphas)
        self.betas = state.get("betas", self.betas)


class BanditOptimizer:
    """Manages per-(campaign_bucket, risk_band) bandits."""

    def __init__(self, offer_types: list, state_path: str = "outputs/bandit_state.json"):
        self.offer_types = offer_types
        self.state_path = state_path
        self.bandits: dict = {}
        self._load_state()

    def _key(self, campaign_bucket: str, risk_band: str) -> str:
        return f"{campaign_bucket}::{risk_band}"

    def _get_or_create(self, campaign_bucket: str, risk_band: str) -> ThompsonSamplingBandit:
        key = self._key(campaign_bucket, risk_band)
        if key not in self.bandits:
            self.bandits[key] = ThompsonSamplingBandit(self.offer_types)
        return self.bandits[key]

    def select_offer_type(self, campaign_bucket: str, risk_band: str) -> str:
        return self._get_or_create(campaign_bucket, risk_band).sample()

    def update(self, campaign_bucket: str, risk_band: str, offer_type: str, redeemed: bool) -> None:
        self._get_or_create(campaign_bucket, risk_band).update(offer_type, redeemed)
        self._save_state()

    def _save_state(self) -> None:
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        state = {key: bandit.get_state() for key, bandit in self.bandits.items()}
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> None:
        if not os.path.exists(self.state_path):
            return
        with open(self.state_path) as f:
            state = json.load(f)
        for key, bandit_state in state.items():
            bandit = ThompsonSamplingBandit(self.offer_types)
            bandit.load_state(bandit_state)
            self.bandits[key] = bandit
