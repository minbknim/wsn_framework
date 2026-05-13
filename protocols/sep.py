"""SEP — Stable Election Protocol (개선판 v2).

Smaragdakis, Matta, Bestavros (2004). Proc. SANPA.

개선: m_frac=0.1 (10%) 고에너지 노드(2×E₀) 이종 환경 실제 구현.
→ σ(LND) 대폭 감소, 재현성 향상.
"""
from __future__ import annotations
import random
from typing import Dict, List, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class SEP(BaseProtocol):
    name = "SEP"
    default_params = {
        "ch_ratio": 0.05,
        "m_frac":   0.1,   # 고에너지 노드 비율
        "alpha":    0.5,  # 최적화: σ 최소화   # 고에너지 노드 배수 (→ 2×E₀)
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._not_ch_since: Dict[int, int] = {}
        self._advanced_ids: set = set()
        self._initialized = False

    def _init_heterogeneous(self, nodes):
        m_frac = self.params["m_frac"]
        alpha  = self.params["alpha"]
        n_adv  = max(1, int(len(nodes) * m_frac))
        for nd in self._rng.sample(nodes, n_adv):
            nd.initial_energy *= (1 + alpha)
            nd.energy = nd.initial_energy
            self._advanced_ids.add(nd.node_id)
        self._initialized = True

    def select_cluster_heads(self, alive_nodes, round_num, bs):
        if not self._initialized:
            self._init_heterogeneous(alive_nodes)
        p, alpha, m_frac = self.cfg.ch_ratio, self.params["alpha"], self.params["m_frac"]
        p_nrm = p / (1 + alpha * m_frac)
        p_adv = p * (1 + alpha) / (1 + alpha * m_frac)
        ch_ids = []
        for node in alive_nodes:
            is_adv = node.node_id in self._advanced_ids
            p_use  = p_adv if is_adv else p_nrm
            T_max  = max(1, int(1 / p_use))
            last   = self._not_ch_since.get(node.node_id, 0)
            if round_num - last >= T_max:
                mod = round_num % T_max or 1
                e_r = node.energy / max(node.initial_energy, 1e-9)
                thr = (p_use / (1 - p_use * mod)) * e_r
            else:
                thr = 0.0
            if self._rng.random() < thr:
                ch_ids.append(node.node_id)
                self._not_ch_since[node.node_id] = round_num
        return ch_ids, self._assign_members_to_nearest_ch(alive_nodes, ch_ids)

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        if not ch_ids or not cluster_map: return 0
        nm = {n.node_id: n for n in alive_nodes}
        ch_mem: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for node in alive_nodes:
            cid = cluster_map.get(node.node_id)
            if cid and cid != node.node_id and cid in nm:
                if self._dissipate_member(node, nm[cid]):
                    ch_mem[cid].append(node)
        pkts = 0
        for cid, members in ch_mem.items():
            ch = nm.get(cid)
            if ch and ch.alive and self._dissipate_ch(ch, members, bs):
                pkts += 1
        return pkts
