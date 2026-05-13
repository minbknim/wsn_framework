"""
GAF — Geographic Adaptive Fidelity (최종판 v2 — 이동성 지원)

Xu, Y., Heidemann, J., & Estrin, D. (2001). MobiCom.

개선:
  - 이동성 노드 지원: 매 rotate_interval 마다 격자 재배정
  - _grid_cell() 동적 재계산 (노드 좌표 변경 반영)
  - 격자 크기 = tx_range / √5 (논문 정확 구현)
"""
from __future__ import annotations
import math, random
from typing import Dict, List, Optional, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class GAF(BaseProtocol):
    """GAF: 가상 격자 + Active 에너지 로테이션 + 이동성 지원."""
    name = "GAF"
    default_params = {
        "tx_range":       50.0,
        "rotate_interval": 10,   # Active 노드 교체 주기 (라운드)
        "mobile":         False,  # 이동성 활성화 여부
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._grid_active: Dict[tuple, int] = {}
        self._last_rotate: int = 0
        self._area: float = 100.0   # 기본값, 첫 호출 시 설정

    def _cell_size(self) -> float:
        return self.params["tx_range"] / math.sqrt(5)

    def _grid_cell(self, node: SensorNode) -> tuple:
        cs = self._cell_size()
        return (int(node.x / cs), int(node.y / cs))

    def _build_grid(self, alive: List[SensorNode]) -> Dict[tuple, List[SensorNode]]:
        grid: Dict[tuple, List[SensorNode]] = {}
        for n in alive:
            c = self._grid_cell(n)
            grid.setdefault(c, []).append(n)
        return grid

    def select_cluster_heads(self, alive, rnd, bs):
        if not alive: return [], {}

        rotate = self.params["rotate_interval"]
        # 이동성 활성화 시 항상 격자 재배정
        should_rotate = (rnd - self._last_rotate >= rotate or
                         self.params.get("mobile", False))

        grid = self._build_grid(alive)
        alive_set = {n.node_id: n for n in alive}
        ch_ids: List[int] = []
        cluster_map: Dict[int, int] = {}

        for cell, members in grid.items():
            alive_m = [m for m in members if m.alive]
            if not alive_m: continue

            if should_rotate or cell not in self._grid_active:
                # 에너지 가중 확률로 Active 선출
                max_e = max(m.energy for m in alive_m)
                if max_e > 0:
                    weights = [m.energy / max_e for m in alive_m]
                    total_w = sum(weights)
                    rv = self._rng.random() * total_w
                    cum = 0.0; active = alive_m[-1]
                    for m, w in zip(alive_m, weights):
                        cum += w
                        if rv <= cum: active = m; break
                else:
                    active = self._rng.choice(alive_m)
                self._grid_active[cell] = active.node_id
            else:
                prev_id = self._grid_active[cell]
                if prev_id in alive_set and alive_set[prev_id].alive:
                    active = alive_set[prev_id]
                else:
                    active = max(alive_m, key=lambda m: m.energy)
                    self._grid_active[cell] = active.node_id

            ch_ids.append(active.node_id)
            for m in alive_m:
                cluster_map[m.node_id] = active.node_id

        if should_rotate: self._last_rotate = rnd
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, rnd) -> int:
        if not ch_ids or not cluster_map: return 0
        node_map = {n.node_id: n for n in alive_nodes}
        tx_range = self.params["tx_range"]
        pkt = self.comm.packet_size
        bs_x, bs_y = bs.x, bs.y
        pkts = 0

        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members and nid in node_map:
                ch_members[cid].append(node_map[nid])

        # Sleep 노드 → Active 노드
        for nd in alive_nodes:
            cid = cluster_map.get(nd.node_id)
            if cid and cid != nd.node_id and cid in node_map:
                ch = node_map[cid]
                if ch.alive:
                    self._dissipate_member(nd, ch)

        # Active → BS (릴레이 또는 직접)
        active_sorted = sorted(
            [node_map[c] for c in ch_ids if c in node_map and node_map[c].alive],
            key=lambda n: n.distance_to_point(bs_x, bs_y))

        for active in active_sorted:
            if not active.alive: continue
            members = ch_members.get(active.node_id, [])
            agg = self.em.agg_energy(pkt * (len(members) + 1))
            if not self._consume(active, agg): continue
            d_bs = active.distance_to_point(bs_x, bs_y)
            if d_bs <= tx_range:
                if self._consume(active, self.em.tx_energy(pkt, d_bs)):
                    pkts += 1
            else:
                closer = [n for n in active_sorted
                          if n.node_id != active.node_id and n.alive
                          and n.distance_to_point(bs_x, bs_y) < d_bs
                          and active.distance_to(n) <= tx_range]
                if closer:
                    relay = min(closer, key=lambda n: n.distance_to_point(bs_x, bs_y))
                    if self._consume(active, self.em.tx_energy(pkt, active.distance_to(relay))):
                        self._consume(relay, self.em.rx_energy(pkt))
                else:
                    if self._consume(active, self.em.tx_energy(pkt, d_bs)):
                        pkts += 1
        return pkts
