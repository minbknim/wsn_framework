"""PEGASIS — Power-Efficient GAthering in Sensor Information Systems.

Lindsey, S., & Raghavendra, C. S. (2002). PEGASIS: Power-efficient gathering
in sensor information systems. Proc. IEEE Aerospace Conf., pp. 3-1125–3-1130.

최적화:
  - 노드 사망이 없으면 체인 재계산 없이 캐시된 체인 재사용 (O(N²) → O(1))
  - nearest-neighbor 방문 시 list 대신 set 사용
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple, Optional, Set

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class PEGASIS(BaseProtocol):
    """그리디 체인 + token-passing. 라운드마다 리더 교체."""
    name = "PEGASIS"
    default_params = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chain: Optional[List[SensorNode]] = None
        self._chain_ids: Optional[frozenset] = None   # 캐시 키
        self._rng = random.Random(42)

    def _build_chain(self, alive_nodes: List[SensorNode]) -> List[SensorNode]:
        """Greedy nearest-neighbor chain (캐시 최적화 포함)."""
        if not alive_nodes:
            return []
        cur_ids = frozenset(n.node_id for n in alive_nodes)
        # 노드 집합 변화 없으면 캐시 재사용
        if self._chain_ids == cur_ids and self._chain:
            return self._chain

        node_map = {n.node_id: n for n in alive_nodes}
        remaining: Set[int] = set(node_map.keys())
        first_id = next(iter(remaining))
        remaining.remove(first_id)
        chain = [node_map[first_id]]

        while remaining:
            last = chain[-1]
            # O(remaining) nearest search
            nearest_id = min(
                remaining,
                key=lambda nid: last.distance_to(node_map[nid])
            )
            chain.append(node_map[nearest_id])
            remaining.remove(nearest_id)

        self._chain = chain
        self._chain_ids = cur_ids
        return chain

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        if not alive_nodes:
            return [], {}
        chain = self._build_chain(alive_nodes)
        # 체인에서 살아있는 노드만
        alive_set = {n.node_id for n in alive_nodes}
        live_chain = [n for n in chain if n.node_id in alive_set]
        if not live_chain:
            return [], {}
        leader_idx = round_num % len(live_chain)
        leader = live_chain[leader_idx]
        ch_ids = [leader.node_id]
        cluster_map = {n.node_id: leader.node_id for n in alive_nodes}
        self._chain = live_chain
        return ch_ids, cluster_map

    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        if not ch_ids or not self._chain:
            return 0
        chain = self._chain
        if not chain:
            return 0
        node_map = {n.node_id: n for n in alive_nodes}
        # token-passing: 체인 순서대로 인접 노드에 전송
        for i in range(len(chain) - 1):
            src, dst = chain[i], chain[i + 1]
            if not src.alive or not dst.alive:
                continue
            tx = self.em.tx_energy(self.comm.packet_size, src.distance_to(dst))
            src.energy -= tx
            if src.energy <= 0: src.energy = 0; src.alive = False
            rx = self.em.rx_energy(self.comm.packet_size)
            dst.energy -= rx
            if dst.energy <= 0: dst.energy = 0; dst.alive = False
        # 리더 → BS
        leader = node_map.get(ch_ids[0])
        if leader and leader.alive:
            dist_bs = leader.distance_to_point(bs.x, bs.y)
            tx = self.em.tx_energy(self.comm.packet_size, dist_bs)
            leader.energy -= tx
            if leader.energy <= 0: leader.energy = 0; leader.alive = False
            return 1
        return 0
