"""TEEN — Threshold-sensitive Energy Efficient sensor Network.

Manjeshwar, A., & Agrawal, D. P. (2001). TEEN: A routing protocol for
enhanced efficiency in wireless sensor networks. Proc. IPDPS, pp. 2009–2015.
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class TEEN(BaseProtocol):
    """하드/소프트 임계값 기반 선택적 전송 반응형 프로토콜."""
    name = "TEEN"
    default_params = {
        "ch_ratio": 0.05,
        "hard_threshold": 0.1,
        "soft_threshold": 0.01,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._not_ch_since: Dict[int, int] = {}

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
        ht = self.params["hard_threshold"]
        st = self.params["soft_threshold"]
        node_map = {n.node_id: n for n in alive_nodes}
        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members and nid in node_map:
                ch_members[cid].append(node_map[nid])
        for node in alive_nodes:
            ch_id = cluster_map.get(node.node_id)
            if ch_id and ch_id != node.node_id and ch_id in node_map:
                ch_node = node_map[ch_id]
                if ch_node.alive and node.energy >= max(0, ht - st):
                    self._dissipate_member(node, ch_node)
        pkts = 0
        for ch_id, members in ch_members.items():
            ch = node_map.get(ch_id)
            if ch and ch.alive:
                self._dissipate_ch(ch, members, bs)
                pkts += 1
        return pkts
