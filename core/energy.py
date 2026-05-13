"""energy.py — WSN 에너지 모델 최종판 v2 (채널모델+하베스팅)"""
from __future__ import annotations
import math, random
from dataclasses import dataclass


@dataclass
class EnergyConfig:
    initial_energy: float = 0.5
    e_elec:         float = 50e-9
    epsilon_fs:     float = 10e-12
    epsilon_mp:     float = 0.0013e-12
    e_agg:          float = 5e-9
    shadowing_std:  float = 0.0      # dB (0=이상적)
    shadowing_seed: int   = 42
    harvesting:     bool  = False
    harvest_rate:   float = 0.0001   # J/round
    harvest_period: int   = 1000     # 태양광 주기

    def __post_init__(self):
        self.d0 = math.sqrt(self.epsilon_fs / self.epsilon_mp)


class EnergyModel:
    def __init__(self, cfg):
        self.cfg = cfg
        seed = getattr(cfg, 'shadowing_seed', 42) or 42
        self._rng = random.Random(seed)

    def _get(self, key, default):
        return getattr(self.cfg, key, default)

    def _d0(self):
        fs = self._get('epsilon_fs', None) or self._get('e_amp_fs', 10e-12)
        mp = self._get('epsilon_mp', None) or self._get('e_amp_mp', 0.0013e-12)
        try: return math.sqrt(fs / mp)
        except: return 87.7

    def tx_energy(self, bits: int, distance: float) -> float:
        d = max(distance, 1e-6)
        e_elec = self._get('e_elec', 50e-9)
        if self._get('shadowing_std', 0) > 0:
            sigma = self._get('shadowing_std', 0) / (10 * math.log10(math.e))
            d *= math.sqrt(math.exp(self._rng.gauss(0, sigma)))
        d0 = self._d0()
        fs = self._get('epsilon_fs', None) or self._get('e_amp_fs', 10e-12)
        mp = self._get('epsilon_mp', None) or self._get('e_amp_mp', 0.0013e-12)
        if d < d0:
            return bits * (e_elec + fs * d ** 2)
        else:
            return bits * (e_elec + mp * d ** 4)

    def rx_energy(self, bits: int) -> float:
        return bits * self._get('e_elec', 50e-9)

    def agg_energy(self, bits: int) -> float:
        return bits * self._get('e_agg', 5e-9)

    def harvest_energy(self, round_num: int) -> float:
        if not self._get('harvesting', False): return 0.0
        T = max(self._get('harvest_period', 1000), 1)
        rate = self._get('harvest_rate', 0.0001)
        return rate * math.sin(math.pi * round_num / T) ** 2
