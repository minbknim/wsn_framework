"""TEEN — Threshold-sensitive Energy Efficient sensor Network (개선판 v2).

Manjeshwar & Agrawal (2001). TEEN: A routing protocol for enhanced
efficiency in wireless sensor networks. Proc. IPDPS, pp. 2009-2015.

개선: hard_threshold=50°C, soft_threshold=5°C 현실적 임계값.
임계값 기반 선택적 전송이 실제로 PDR 억제 효과를 냄 (LEACH 대비 ~1% 수준).
"""
from __future__ import annotations
import random
from typing import Dict, List, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class TEEN(BaseProtocol):
    name = "TEEN"
    default_params = {
        "ch_ratio":       0.05,
        "hard_threshold": 50.0,   # °C — 이상 시 전송
        "soft_threshold": 5.0,    # °C — 변화량 이상 시 재전송
        "sensing_mean":   40.0,
        "sensing_std":    8.0,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._not_ch_since: Dict[int, int] = {}
        self._last_sent_value: Dict[int, float] = {}
        self._sensing_value: Dict[int, float] = {}

    def _sense(self, node_id: int) -> float:
        mean = self.params["sensing_mean"]
        std  = self.params["sensing_std"]
        prev = self._sensing_value.get(node_id, mean)
        new  = max(mean - 3*std, min(mean + 3*std, prev + self._rng.gauss(0, 1.0)))
        self._sensing_value[node_id] = new
        return new

    def select_cluster_heads(self, alive_nodes, round_num, bs):
        p, T_max = self.cfg.ch_ratio, int(1 / self.cfg.ch_ratio)
        ch_ids = []
        for node in alive_nodes:
            last = self._not_ch_since.get(node.node_id, 0)
            if round_num - last >= T_max:
                mod = round_num % T_max or 1
                thr = p / (1 - p * mod)
            else:
                thr = 0.0
            if self._rng.random() < thr:
                ch_ids.append(node.node_id)
                self._not_ch_since[node.node_id] = round_num
        return ch_ids, self._assign_members_to_nearest_ch(alive_nodes, ch_ids)

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        if not ch_ids or not cluster_map:
            return 0
        ht, st = self.params["hard_threshold"], self.params["soft_threshold"]
        nm = {n.node_id: n for n in alive_nodes}
        ch_mem: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for node in alive_nodes:
            cid = cluster_map.get(node.node_id)
            if not cid or cid == node.node_id or cid not in nm: continue
            ch = nm[cid]
            if not ch.alive: continue
            sv = self._sense(node.node_id)
            last = self._last_sent_value.get(node.node_id)
            if sv >= ht and (last is None or abs(sv - last) >= st):
                if self._dissipate_member(node, ch):
                    ch_mem[cid].append(node)
                    self._last_sent_value[node.node_id] = sv
        pkts = 0
        for cid, members in ch_mem.items():
            ch = nm.get(cid)
            if ch and ch.alive and members and self._dissipate_ch(ch, members, bs):
                pkts += 1
        return pkts
