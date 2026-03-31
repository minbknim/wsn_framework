"""First-order radio energy model (Heinzelman et al.)."""
from __future__ import annotations
import math
from .config import EnergyConfig


class EnergyModel:
    """
    ETx(k, d) = k * E_elec + k * eps_amp * d^n
    ERx(k)    = k * E_elec
    EDA(k)    = k * E_agg          (data aggregation at CH)

    Threshold distance d0 = sqrt(eps_fs / eps_mp)
      d < d0  → free-space  (d²)
      d ≥ d0  → multipath   (d⁴)
    """

    def __init__(self, cfg: EnergyConfig):
        self.cfg = cfg
        self.d0  = math.sqrt(cfg.e_amp_fs / cfg.e_amp_mp)

    # ── Transmission ─────────────────────────────────────────────────────────

    def tx_energy(self, k_bits: int, distance: float) -> float:
        if distance < self.d0:
            return k_bits * self.cfg.e_elec + k_bits * self.cfg.e_amp_fs * distance ** 2
        else:
            return k_bits * self.cfg.e_elec + k_bits * self.cfg.e_amp_mp * distance ** 4

    # ── Reception ────────────────────────────────────────────────────────────

    def rx_energy(self, k_bits: int) -> float:
        return k_bits * self.cfg.e_elec

    # ── Data aggregation (at cluster head) ───────────────────────────────────

    def agg_energy(self, k_bits: int) -> float:
        return k_bits * self.cfg.e_agg

    # ── Threshold distance ───────────────────────────────────────────────────

    @property
    def threshold_distance(self) -> float:
        return self.d0

    # ── CH round energy cost ─────────────────────────────────────────────────

    def ch_round_energy(
        self, k_bits: int, n_cluster_members: int, dist_to_bs: float
    ) -> float:
        """Total energy cost for a CH in one round."""
        rx  = self.rx_energy(k_bits) * n_cluster_members
        agg = self.agg_energy(k_bits * (n_cluster_members + 1))
        tx  = self.tx_energy(k_bits * (n_cluster_members + 1), dist_to_bs)
        return rx + agg + tx

    def member_round_energy(
        self, k_bits: int, dist_to_ch: float
    ) -> float:
        """Energy cost for a regular node (member) in one round."""
        return self.tx_energy(k_bits, dist_to_ch)
