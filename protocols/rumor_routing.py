"""
Rumor Routing (최종판 v3)

Braginsky & Estrin (2002). WSNA, pp. 22-31.

개선:
  - 경로테이블 기반 next-hop 가중결합 (이벤트 경로 실제 활용)
  - agent_hops=3 유지 (v2 최적화)
  - _consume() 에너지 음수 방지
"""
from __future__ import annotations
import random
from typing import Dict, List, Optional, Set, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class RumorRouting(BaseProtocol):
    """Rumor Routing: 경로테이블+Greedy 가중결합 BS 전달."""
    name = "RUMOR"
    default_params = {
        "agent_hops":   3,
        "n_agents":     2,
        "event_prob":   0.1,
        "tx_range":     50.0,
        "route_weight": 0.6,   # 경로테이블 vs Greedy 가중치
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._route_table: Dict[int, Optional[int]] = {}   # nid → next_hop_id
        self._hop_dist:    Dict[int, int]           = {}   # nid → BS까지 홉수

    def _neighbors(self, node: SensorNode,
                    alive: List[SensorNode]) -> List[SensorNode]:
        tx = self.params["tx_range"]
        return [n for n in alive
                if n.node_id != node.node_id
                and node.distance_to(n) <= tx and n.alive]

    def _agent_walk(self, start: SensorNode, alive: List[SensorNode],
                    bs: BaseStation) -> None:
        """에이전트 랜덤워크 — 경로테이블 및 홉거리 갱신."""
        ctrl = self.comm.ctrl_packet_size
        current = start
        visited: Set[int] = {start.node_id}
        self._route_table[start.node_id] = None
        self._hop_dist[start.node_id] = self._hop_dist.get(start.node_id, 0)

        for hop in range(self.params["agent_hops"]):
            if not current.alive: break
            nbrs = [n for n in self._neighbors(current, alive)
                    if n.node_id not in visited]
            if not nbrs: break
            nxt = self._rng.choice(nbrs)
            visited.add(nxt.node_id)

            if not self._consume(current,
                                  self.em.tx_energy(ctrl, current.distance_to(nxt))):
                break
            self._consume(nxt, self.em.rx_energy(ctrl))
            if not nxt.alive: break

            # 경로테이블: 에이전트 경로를 역방향으로 BS까지 홉 기록
            if nxt.node_id not in self._route_table:
                self._route_table[nxt.node_id] = current.node_id
            self._hop_dist[nxt.node_id] = hop + 1
            current = nxt

    def _best_next_hop(self, current: SensorNode,
                        alive: List[SensorNode], bs: BaseStation,
                        d_bs: float) -> Optional[SensorNode]:
        """경로테이블 + Greedy 가중결합으로 최적 next-hop 선택."""
        nbrs = self._neighbors(current, alive)
        closer = [n for n in nbrs
                  if n.distance_to_point(bs.x, bs.y) < d_bs]
        if not closer:
            return None

        w = self.params["route_weight"]
        best, best_score = None, float("inf")
        for n in closer:
            # Greedy 점수: BS까지 거리 정규화
            greedy = n.distance_to_point(bs.x, bs.y) / d_bs
            # 경로테이블 점수: 알려진 홉수가 짧을수록 좋음
            hop_val = self._hop_dist.get(n.node_id, 99) / 20.0
            score = w * hop_val + (1 - w) * greedy
            if score < best_score:
                best_score, best = score, n
        return best

    def select_cluster_heads(self, alive, rnd, bs):
        if not alive: return [], {}
        p   = self.params["event_prob"]
        evs = [n for n in alive if self._rng.random() < p]
        if not evs: evs = [self._rng.choice(alive)]
        ch_ids = [n.node_id for n in evs]
        return ch_ids, {n.node_id: n.node_id for n in alive}

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, rnd) -> int:
        if not ch_ids or not alive_nodes: return 0
        node_map = {n.node_id: n for n in alive_nodes}
        pkt  = self.comm.packet_size
        tx_r = self.params["tx_range"]
        pkts = 0

        for eid in ch_ids:
            ev = node_map.get(eid)
            if not ev or not ev.alive: continue

            for _ in range(self.params["n_agents"]):
                self._agent_walk(ev, alive_nodes, bs)

            current = ev
            for _ in range(20):
                if not current.alive: break
                d_bs = current.distance_to_point(bs.x, bs.y)
                if d_bs <= tx_r * 2:
                    if self._consume(current, self.em.tx_energy(pkt, d_bs)):
                        pkts += 1
                    break
                nxt = self._best_next_hop(current, alive_nodes, bs, d_bs)
                if nxt is None: break
                if not self._consume(current,
                                     self.em.tx_energy(pkt, current.distance_to(nxt))):
                    break
                self._consume(nxt, self.em.rx_energy(pkt))
                current = nxt
        return pkts
