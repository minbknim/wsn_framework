"""
GAF — Geographic Adaptive Fidelity

Xu, Y., Heidemann, J., & Estrin, D. (2001).
Geography-informed energy conservation for ad hoc routing.
Proc. 7th Annual ACM/IEEE Int. Conf. Mobile Computing and Networking (MobiCom), pp. 70–84.
DOI:10.1145/381677.381695

핵심 알고리즘:
  1. 센서 필드를 가상 격자(virtual grid)로 분할
     격자 크기: r / √5 (r=전송 반경) — 격자 대각선 ≤ r 보장
  2. 각 격자 셀에서 1개 노드만 활성화(Active), 나머지는 슬립(Sleep)
  3. Active 노드는 주기적으로 교체 (에너지 균등화)
     교체 시 잔여 에너지 많은 노드 우선
  4. Active 노드만 데이터 수집·전송 → 슬립 노드는 에너지 절약

에너지 모델:
  - Active 노드: 데이터 전송/수신 에너지 소모
  - Sleep 노드: 최소 대기 에너지 (idle 에너지는 무시, First-order 모델 적용)
  - 격자 간 라우팅: Active 노드들이 BS 방향으로 릴레이

프레임워크 적응:
  - 격자 크기: tx_range / √5
  - 격자별 Active 노드 = CH
  - Active 노드들이 BS 방향으로 멀티홉 라우팅
"""
from __future__ import annotations
import math
import random
from typing import List, Dict, Tuple, Optional

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class GAF(BaseProtocol):
    """
    GAF: 가상 격자 기반 에너지 절약 라우팅.

    격자당 1개 Active 노드만 전송, 나머지는 슬립.
    Active 노드를 에너지 비례로 주기 교체.
    """
    name = "GAF"
    default_params = {
        "tx_range":    35.0,   # 전송 반경 (m)
        "rotate_interval": 10, # Active 노드 교체 주기 (라운드)
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._grid_active: Dict[tuple, int] = {}  # (gx,gy) → active node_id
        self._last_rotate: int = 0

    def _grid_cell(self, node: SensorNode, cell_size: float) -> tuple:
        """노드가 속하는 격자 셀 (gx, gy)."""
        gx = int(node.x / cell_size)
        gy = int(node.y / cell_size)
        return (gx, gy)

    def _build_grid(
        self, alive_nodes: List[SensorNode], cell_size: float, round_num: int
    ) -> Dict[tuple, List[SensorNode]]:
        """격자별 노드 그룹화."""
        grid: Dict[tuple, List[SensorNode]] = {}
        for n in alive_nodes:
            cell = self._grid_cell(n, cell_size)
            grid.setdefault(cell, []).append(n)
        return grid

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        """격자별 Active 노드를 CH로 선출."""
        if not alive_nodes:
            return [], {}

        tx_range  = self.params["tx_range"]
        rotate_k  = self.params["rotate_interval"]
        # GAF 논문 격자 크기: r/√5
        cell_size = tx_range / math.sqrt(5)

        grid = self._build_grid(alive_nodes, cell_size, round_num)
        alive_set = {n.node_id: n for n in alive_nodes}

        # 교체 주기마다 Active 노드 재선출
        should_rotate = (round_num - self._last_rotate >= rotate_k)

        ch_ids: List[int] = []
        cluster_map: Dict[int, int] = {}

        for cell, members in grid.items():
            alive_members = [m for m in members if m.alive]
            if not alive_members:
                continue

            if should_rotate or cell not in self._grid_active:
                # 에너지 가중 확률로 Active 노드 선택
                max_e = max(m.energy for m in alive_members)
                if max_e > 0:
                    # 에너지 많은 노드 우선 (확률적)
                    weights = [m.energy / max_e for m in alive_members]
                    total_w = sum(weights)
                    r_val   = self._rng.random() * total_w
                    cum = 0.0
                    active = alive_members[-1]
                    for m, w in zip(alive_members, weights):
                        cum += w
                        if r_val <= cum:
                            active = m
                            break
                else:
                    active = self._rng.choice(alive_members)

                self._grid_active[cell] = active.node_id
            else:
                # 기존 Active 노드가 살아있으면 유지
                prev_id = self._grid_active[cell]
                if prev_id in alive_set and alive_set[prev_id].alive:
                    active = alive_set[prev_id]
                else:
                    # 사망 시 재선출
                    active = max(alive_members, key=lambda m: m.energy)
                    self._grid_active[cell] = active.node_id

            ch_ids.append(active.node_id)
            for m in alive_members:
                cluster_map[m.node_id] = active.node_id

        if should_rotate:
            self._last_rotate = round_num

        return ch_ids, cluster_map

    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        if not ch_ids or not cluster_map:
            return 0

        node_map = {n.node_id: n for n in alive_nodes}
        tx_range  = self.params["tx_range"]
        cell_size = tx_range / math.sqrt(5)
        pkt       = self.comm.packet_size
        bs_x, bs_y = bs.x, bs.y
        pkts_to_bs = 0

        # Sleep 노드(비Active) → Active 노드 데이터 전송
        ch_set = set(ch_ids)
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

        # Active 노드가 데이터 집계 후 BS 방향으로 라우팅
        active_nodes = [node_map[cid] for cid in ch_ids
                        if cid in node_map and node_map[cid].alive]

        # BS 거리 기준 정렬 (가까운 Active 먼저)
        active_sorted = sorted(
            active_nodes,
            key=lambda n: n.distance_to_point(bs_x, bs_y)
        )

        for active in active_sorted:
            if not active.alive:
                continue

            members = ch_members.get(active.node_id, [])
            n_mem   = len(members)

            # 집계 에너지
            agg = self.em.agg_energy(pkt * (n_mem + 1))
            active.energy -= agg
            if active.energy <= 0:
                active.energy = 0; active.alive = False; continue

            d_bs = active.distance_to_point(bs_x, bs_y)

            if d_bs <= tx_range:
                # BS 직접 전송
                tx = self.em.tx_energy(pkt, d_bs)
                active.energy -= tx
                if active.energy <= 0:
                    active.energy = 0; active.alive = False; continue
                pkts_to_bs += 1
            else:
                # 더 가까운 Active 노드로 릴레이
                closer = [
                    n for n in active_sorted
                    if n.node_id != active.node_id
                    and n.alive
                    and n.distance_to_point(bs_x, bs_y) < d_bs
                    and active.distance_to(n) <= tx_range
                ]
                if closer:
                    relay = min(closer, key=lambda n: n.distance_to_point(bs_x, bs_y))
                    tx = self.em.tx_energy(pkt, active.distance_to(relay))
                    active.energy -= tx
                    if active.energy <= 0:
                        active.energy = 0; active.alive = False; continue
                    rx = self.em.rx_energy(pkt)
                    relay.energy -= rx
                    if relay.energy <= 0:
                        relay.energy = 0; relay.alive = False
                else:
                    # 릴레이 없음 → 직접 전송 (거리 무관)
                    tx = self.em.tx_energy(pkt, d_bs)
                    active.energy -= tx
                    if active.energy <= 0:
                        active.energy = 0; active.alive = False; continue
                    pkts_to_bs += 1

        return pkts_to_bs
