"""DEEC — Distributed Energy-Efficient Clustering.

Qing, L., Zhu, Q., & Wang, M. (2006). Design of a distributed energy-efficient
clustering algorithm for heterogeneous wireless sensor networks.
Computer Communications, 29(12), 2230–2237.

이상적 에너지 소비량 기반 동적 CH 확률 조정. 이종(heterogeneous) 네트워크 최적.
"""
from __future__ import annotations
import math
import random
from typing import List, Dict, Tuple

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class DEEC(BaseProtocol):
    """잔여 에너지 vs 이상적 에너지 소비 비율로 CH 확률 동적 결정."""
    name = "DEEC"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._total_initial: float = 0.0
        self._initialized = False

    def _init_total_energy(self, alive_nodes: List[SensorNode]) -> None:
        if not self._initialized:
            self._total_initial = sum(n.initial_energy for n in alive_nodes)
            self._initialized = True

    def _ideal_energy_per_round(self, n_nodes: int) -> float:
        """
        E_ideal(r) = E_total / (n * r) per round
        간소화: E_total * p / n (n_nodes 기준)
        """
        if n_nodes == 0:
            return 1e-9
        return self._total_initial * self.cfg.ch_ratio / n_nodes

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        if not alive_nodes:
            return [], {}
        self._init_total_energy(alive_nodes)

        # 현재 총 잔여 에너지
        total_residual = sum(n.energy for n in alive_nodes)
        n = len(alive_nodes)
        p = self.cfg.ch_ratio

        ch_ids = []
        for node in alive_nodes:
            if total_residual <= 0:
                break
            # DEEC 확률: p_i = p * E_i(r) / E_avg(r)
            e_avg = total_residual / n
            prob = p * (node.energy / e_avg) if e_avg > 0 else p

            # epoch 기반 임계값
            epoch = max(1, round(1.0 / prob)) if prob > 0 else 20
            mod = round_num % epoch or 1
            denom = 1 - prob * mod
            threshold = prob / denom if denom > 0 else 0.0
            threshold = max(0.0, min(1.0, threshold))

            if self._rng.random() < threshold:
                ch_ids.append(node.node_id)

        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        from .leach import LEACH
        return LEACH.run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num)
