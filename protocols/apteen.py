"""APTEEN — Adaptive Periodic Threshold-sensitive Energy Efficient Network.

Manjeshwar, A., & Agrawal, D. P. (2002). APTEEN: A hybrid protocol for
efficient routing and comprehensive information retrieval in wireless sensor
networks. Proc. IPDPS, pp. 195–202.

TEEN + 주기적 강제 전송 결합. 주기(count_time)마다 임계값 미달 노드도 강제 전송.
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class APTEEN(BaseProtocol):
    """TEEN의 반응형 + 주기적 전송 결합 하이브리드."""
    name = "APTEEN"
    default_params = {
        "ch_ratio":       0.05,
        "hard_threshold": 0.1,
        "soft_threshold": 0.01,
        "count_time":     5,    # 강제 전송 주기 (라운드)
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._not_ch_since: Dict[int, int] = {}
        self._last_forced: Dict[int, int] = {}  # 마지막 강제 전송 라운드

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        p = self.cfg.ch_ratio
        T_max = int(1 / p)
        ch_ids = []
        for node in alive_nodes:
            last = self._not_ch_since.get(node.node_id, 0)
            if round_num - last >= T_max:
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
        ht  = self.params["hard_threshold"]
        st  = self.params["soft_threshold"]
        ct  = self.params["count_time"]
        node_map = {n.node_id: n for n in alive_nodes}
        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members and nid in node_map:
                ch_members[cid].append(node_map[nid])

        for node in alive_nodes:
            ch_id = cluster_map.get(node.node_id)
            if not ch_id or ch_id == node.node_id:
                continue
            ch_node = node_map.get(ch_id)
            if not ch_node or not ch_node.alive:
                continue
            # 임계값 조건 OR 주기적 강제 전송
            last_forced = self._last_forced.get(node.node_id, 0)
            periodic_due = (round_num - last_forced) >= ct
            energy_ok = node.energy >= max(0, ht - st)

            if energy_ok or periodic_due:
                self._dissipate_member(node, ch_node)
                if periodic_due:
                    self._last_forced[node.node_id] = round_num

        pkts = 0
        for ch_id, members in ch_members.items():
            ch = node_map.get(ch_id)
            if ch and ch.alive:
                self._dissipate_ch(ch, members, bs)
                pkts += 1
        return pkts
