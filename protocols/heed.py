"""HEED — Hybrid Energy-Efficient Distributed Clustering.

Younis, O., & Fahmy, S. (2004). HEED: A hybrid, energy-efficient, distributed
clustering approach. IEEE Trans. Mobile Computing, 3(4), 366–379.
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class HEED(BaseProtocol):
    """잔여 에너지 비례 CH 확률. O(1) 반복 수렴."""
    name = "HEED"
    default_params = {"ch_ratio": 0.05, "c_prob_min": 0.001}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        max_e = max(n.initial_energy for n in alive_nodes)
        ch_ids = []
        for node in alive_nodes:
            ch_prob = self.cfg.ch_ratio * (node.energy / max_e)
            ch_prob = max(ch_prob, self.params["c_prob_min"])
            if self._rng.random() < ch_prob:
                ch_ids.append(node.node_id)
        if not ch_ids and alive_nodes:
            best = max(alive_nodes, key=lambda n: n.energy)
            ch_ids = [best.node_id]
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        from .leach import LEACH
        return LEACH.run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num)
