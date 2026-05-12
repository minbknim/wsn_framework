"""LEACH — Low-Energy Adaptive Clustering Hierarchy.

Heinzelman, W. R., Chandrakasan, A., & Balakrishnan, H. (2000).
Energy-efficient communication protocol for wireless microsensor networks.
Proc. HICSS-33.
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class LEACH(BaseProtocol):
    """확률적 임계값 기반 CH 선출. epoch(=1/p 라운드)마다 재선출."""
    name = "LEACH"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._not_ch_since: Dict[int, int] = {}
        self._rng = random.Random(42)

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        p = self.cfg.ch_ratio
        T_max = int(1 / p)
        ch_ids = []
        for node in alive_nodes:
            last = self._not_ch_since.get(node.node_id, 0)
            rounds_since = round_num - last
            if rounds_since >= T_max:
                mod = round_num % T_max or 1
                threshold = p / (1 - p * mod)
            else:
                threshold = 0.0
            if self._rng.random() < threshold:
                ch_ids.append(node.node_id)
                self._not_ch_since[node.node_id] = round_num
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        if not ch_ids or not cluster_map:
            return 0
        node_map = {n.node_id: n for n in alive_nodes}
        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members:
                ch_members[cid].append(node_map[nid])
        for node in alive_nodes:
            ch_id = cluster_map.get(node.node_id)
            if ch_id and ch_id != node.node_id and ch_id in node_map:
                ch_node = node_map[ch_id]
                if ch_node.alive:
                    self._dissipate_member(node, ch_node)
        pkts = 0
        for ch_id, members in ch_members.items():
            ch = node_map.get(ch_id)
            if ch and ch.alive:
                self._dissipate_ch(ch, members, bs)
                pkts += 1
        return pkts
