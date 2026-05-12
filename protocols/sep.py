"""SEP — Stable Election Protocol.

Smaragdakis, G., Matta, I., & Bestavros, A. (2004). SEP: A stable election
protocol for clustered heterogeneous wireless sensor networks. Proc. SANPA.
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class SEP(BaseProtocol):
    """이종 노드: 잔여 에너지 가중 CH 선출 확률."""
    name = "SEP"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        p = self.cfg.ch_ratio
        ch_ids = []
        for node in alive_nodes:
            epoch = max(1, int(1 / p))
            weighted_p = p * (node.energy / node.initial_energy)
            rnd_in_epoch = round_num % epoch or 1
            denom = 1 - weighted_p * rnd_in_epoch
            threshold = weighted_p / denom if denom > 0 else 0.0
            threshold = max(0.0, threshold)
            if self._rng.random() < threshold:
                ch_ids.append(node.node_id)
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        from .leach import LEACH
        return LEACH.run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num)
