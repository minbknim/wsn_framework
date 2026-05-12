"""EE-LEACH — Energy-Efficient LEACH with Multi-Hop inter-cluster routing.

CHs 간 릴레이 라우팅으로 장거리 BS 전송 비용 절감.
최적화: CH 트리 결과 캐싱, numpy 거리 계산 제거.
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple, Optional, FrozenSet

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class EE_LEACH(BaseProtocol):
    """멀티홉 CH 간 릴레이로 장거리 전송 에너지 절감."""
    name = "EE-LEACH"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._not_ch_since: Dict[int, int] = {}
        # CH 트리 캐시 (CH 집합이 같으면 재사용)
        self._parent_cache: Dict[int, Optional[int]] = {}
        self._parent_cache_key: Optional[FrozenSet[int]] = None

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

    def _build_ch_tree(
        self, ch_ids: List[int], node_map: Dict[int, SensorNode], bs: BaseStation
    ) -> Dict[int, Optional[int]]:
        """각 CH의 부모 CH 결정 (BS에 더 가까운 CH로 릴레이). 캐시 사용."""
        key = frozenset(ch_ids)
        if key == self._parent_cache_key:
            return self._parent_cache

        parent: Dict[int, Optional[int]] = {}
        # CH별 BS 거리 사전 계산
        ch_dist_bs = {
            cid: node_map[cid].distance_to_point(bs.x, bs.y)
            for cid in ch_ids if cid in node_map
        }
        for cid in ch_ids:
            if cid not in node_map:
                parent[cid] = None
                continue
            ch = node_map[cid]
            my_dist = ch_dist_bs.get(cid, float('inf'))
            # 나보다 BS에 가까운 CH 중 내게 가장 가까운 것 선택
            best_relay = None
            best_dist  = float('inf')
            for other_id, other_dist_bs in ch_dist_bs.items():
                if other_id == cid:
                    continue
                if other_dist_bs < my_dist:
                    d = ch.distance_to(node_map[other_id])
                    if d < best_dist:
                        best_dist  = d
                        best_relay = other_id
            parent[cid] = best_relay

        self._parent_cache = parent
        self._parent_cache_key = key
        return parent

    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        if not ch_ids or not cluster_map:
            return 0
        node_map = {n.node_id: n for n in alive_nodes}
        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members and nid in node_map:
                ch_members[cid].append(node_map[nid])

        # 멤버 → CH 전송
        for node in alive_nodes:
            cid = cluster_map.get(node.node_id)
            if cid and cid != node.node_id and cid in node_map:
                ch = node_map[cid]
                if ch.alive:
                    self._dissipate_member(node, ch)

        # CH 집계 + 멀티홉 릴레이
        alive_chs = [node_map[cid] for cid in ch_ids
                     if cid in node_map and node_map[cid].alive]
        if not alive_chs:
            return 0

        parent_map = self._build_ch_tree(ch_ids, node_map, bs)
        pkts = 0

        for ch in alive_chs:
            if not ch.alive:
                continue
            members = ch_members.get(ch.node_id, [])
            # 집계
            agg = self.em.agg_energy(self.comm.packet_size * (len(members) + 1))
            ch.energy -= agg
            if ch.energy <= 0:
                ch.energy = 0; ch.alive = False; continue

            relay_id = parent_map.get(ch.node_id)
            relay = node_map.get(relay_id) if relay_id else None

            if relay and relay.alive:
                # 릴레이 CH로 전송
                tx = self.em.tx_energy(self.comm.packet_size, ch.distance_to(relay))
                ch.energy -= tx
                if ch.energy <= 0:
                    ch.energy = 0; ch.alive = False; continue
                rx = self.em.rx_energy(self.comm.packet_size)
                relay.energy -= rx
                if relay.energy <= 0:
                    relay.energy = 0; relay.alive = False
            else:
                # 직접 BS 전송
                tx = self.em.tx_energy(
                    self.comm.packet_size, ch.distance_to_point(bs.x, bs.y))
                ch.energy -= tx
                if ch.energy <= 0:
                    ch.energy = 0; ch.alive = False; continue
                pkts += 1

        return pkts
