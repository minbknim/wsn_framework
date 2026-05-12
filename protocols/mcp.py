"""MCP — Multi-Chain PEGASIS using Relative Distance.

Min, B. G., Park, J. S., Shon, J. G., & Kim, H. G. (2019).
Improvement of Multi-Chain PEGASIS using Relative Distance.

핵심 알고리즘:
  1. RD(i) = d(i, BS) / max(E_i, ε)  — GPS 불필요
  2. RD 기준 레벨 분할 → 멀티체인 구성
  3. 레벨 내 최단거리 greedy 체인
  4. 잔여 에너지 최대 노드를 리더로 선출
  5. MCP+: 차분 전송 (패킷 크기 절반)

최적화: 노드 집합 변화 없으면 체인 캐시 재사용
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, FrozenSet

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


@dataclass
class ChainInfo:
    chain_id: int
    nodes: List[int] = field(default_factory=list)
    leader_id: Optional[int] = None


class MCP(BaseProtocol):
    """Multi-Chain PEGASIS (MCP / MCP+)."""
    name = "MCP"
    default_params = {
        "num_levels":    None,   # None → auto (≈ sqrt(N)/2)
        "differential":  False,  # True → MCP+
        "bs_dist_scale": 1.0,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._chains: List[ChainInfo] = []
        self._cached_ids: Optional[FrozenSet[int]] = None  # 캐시 키

    # ── 상대거리 계산 ─────────────────────────────────────────────────────────
    def _rd(self, node: SensorNode, bs: BaseStation) -> float:
        dist = node.distance_to_point(bs.x, bs.y)
        return dist / max(node.energy, 1e-9) * self.params["bs_dist_scale"]

    # ── 멀티체인 구성 (캐시 포함) ────────────────────────────────────────────
    def _build_multi_chains(
        self, alive_nodes: List[SensorNode], bs: BaseStation
    ) -> List[ChainInfo]:
        cur_ids = frozenset(n.node_id for n in alive_nodes)
        # 노드 집합 변화 없으면 캐시 재사용
        if self._cached_ids == cur_ids and self._chains:
            return self._chains

        n = len(alive_nodes)
        num_levels = self.params["num_levels"] or max(2, round(math.sqrt(n) / 2))
        num_levels = min(num_levels, n)

        # 1) RD 정렬
        rd_vals = {node.node_id: self._rd(node, bs) for node in alive_nodes}
        sorted_nodes = sorted(alive_nodes, key=lambda nd: rd_vals[nd.node_id])
        rds = [rd_vals[nd.node_id] for nd in sorted_nodes]
        rd_min, rd_max = rds[0], rds[-1]
        rd_range = rd_max - rd_min if rd_max > rd_min else 1.0

        # 2) 레벨 배치
        levels: List[List[SensorNode]] = [[] for _ in range(num_levels)]
        for nd in sorted_nodes:
            idx = int((rd_vals[nd.node_id] - rd_min) / (rd_range / num_levels + 1e-12))
            idx = min(idx, num_levels - 1)
            levels[idx].append(nd)

        # 3) 레벨별 greedy 체인
        chains: List[ChainInfo] = []
        for ci, lvl_nodes in enumerate(levels):
            if not lvl_nodes:
                continue
            chain_nodes = self._greedy_chain(lvl_nodes)
            leader = max(chain_nodes, key=lambda nd: nd.energy)
            chains.append(ChainInfo(
                chain_id=ci,
                nodes=[nd.node_id for nd in chain_nodes],
                leader_id=leader.node_id,
            ))

        self._chains = chains
        self._cached_ids = cur_ids
        return chains

    def _greedy_chain(self, nodes: List[SensorNode]) -> List[SensorNode]:
        if not nodes:
            return []
        node_map = {nd.node_id: nd for nd in nodes}
        remaining = set(node_map.keys())
        first = next(iter(remaining))
        remaining.remove(first)
        chain = [node_map[first]]
        while remaining:
            last = chain[-1]
            nxt = min(remaining, key=lambda nid: last.distance_to(node_map[nid]))
            chain.append(node_map[nxt])
            remaining.remove(nxt)
        return chain

    # ── CH 선출 ───────────────────────────────────────────────────────────────
    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        if not alive_nodes:
            return [], {}

        chains = self._build_multi_chains(alive_nodes, bs)
        node_map = {nd.node_id: nd for nd in alive_nodes}
        alive_set = set(node_map.keys())

        ch_ids: List[int] = []
        cluster_map: Dict[int, int] = {}

        for chain in chains:
            chain_alive = [
                node_map[nid] for nid in chain.nodes
                if nid in alive_set
            ]
            if not chain_alive:
                continue
            # 매 라운드 에너지 최대 노드를 리더로 재선출
            leader = max(chain_alive, key=lambda nd: nd.energy)
            chain.leader_id = leader.node_id
            ch_ids.append(leader.node_id)
            for nd in chain_alive:
                cluster_map[nd.node_id] = leader.node_id

        # 미배정 노드 → 가장 가까운 리더
        if ch_ids:
            leader_nodes = [node_map[cid] for cid in ch_ids if cid in node_map]
            for nd in alive_nodes:
                if nd.node_id not in cluster_map:
                    best = min(leader_nodes, key=lambda l: nd.distance_to(l))
                    cluster_map[nd.node_id] = best.node_id

        return ch_ids, cluster_map

    # ── 라운드 실행 ───────────────────────────────────────────────────────────
    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        if not ch_ids or not self._chains:
            return 0

        node_map = {nd.node_id: nd for nd in alive_nodes}
        alive_set = set(node_map.keys())
        diff = self.params["differential"]
        pkt  = self.comm.packet_size // 2 if diff else self.comm.packet_size
        pkts = 0

        for chain in self._chains:
            chain_alive = [
                node_map[nid] for nid in chain.nodes if nid in alive_set
            ]
            if not chain_alive or chain.leader_id not in node_map:
                continue
            leader = node_map[chain.leader_id]
            if not leader.alive:
                continue

            # token-passing
            for i in range(len(chain_alive) - 1):
                src, dst = chain_alive[i], chain_alive[i + 1]
                if not src.alive or not dst.alive:
                    continue
                tx = self.em.tx_energy(pkt, src.distance_to(dst))
                src.energy -= tx
                if src.energy <= 0: src.energy = 0; src.alive = False
                rx = self.em.rx_energy(pkt)
                dst.energy -= rx
                if dst.energy <= 0: dst.energy = 0; dst.alive = False

            if not leader.alive:
                continue
            # 집계 에너지
            agg = self.em.agg_energy(pkt * max(1, len(chain_alive) - 1))
            leader.energy -= agg
            if leader.energy <= 0: leader.energy = 0; leader.alive = False; continue
            # BS 전송
            tx = self.em.tx_energy(pkt, leader.distance_to_point(bs.x, bs.y))
            leader.energy -= tx
            if leader.energy <= 0: leader.energy = 0; leader.alive = False; continue
            pkts += 1

        return pkts


class MCP_PLUS(MCP):
    """MCP+ — 차분 데이터 전송으로 추가 에너지 절감."""
    name = "MCP+"
    default_params = {**MCP.default_params, "differential": True}
