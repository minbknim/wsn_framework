"""
GEAR — Geographic and Energy Aware Routing (최종판 v3)

Yu, Y., Govindan, R., & Estrin, D. (2001). UCLA-CSD TR-01-0023.

개선:
  - _validate_params() 실제 구현 — tx_range < d_max*0.4이면 자동 조정
  - tx_range 기본값 50m
  - _consume() 에너지 음수 방지
"""
from __future__ import annotations
import math, random
from typing import List, Dict, Tuple
from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class GEAR(BaseProtocol):
    """GEAR: h(n)=α·d(n,BS)/d_max + (1-α)·E_consumed"""
    name = "GEAR"
    default_params = {
        "alpha":    0.5,
        "tx_range": 50.0,   # ← 최적값 (100×100m² 환경)
        "sources_per_round": 5,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._validated = False

    def _validate_params(self, alive_nodes: List[SensorNode],
                          bs: BaseStation) -> None:
        """tx_range 자동 검증 — 첫 호출 시 1회 실행."""
        if self._validated:
            return
        tx = self.params["tx_range"]
        if alive_nodes:
            d_max = max(n.distance_to_point(bs.x, bs.y) for n in alive_nodes)
            if d_max > 0 and tx < d_max * 0.4:
                new_tx = round(d_max * 0.5, 1)
                self.params["tx_range"] = new_tx
        self._validated = True

    def _adjusted_cost(self, node: SensorNode,
                        bs: BaseStation, d_max: float) -> float:
        alpha = self.params["alpha"]
        d     = node.distance_to_point(bs.x, bs.y)
        return (alpha * d / d_max +
                (1 - alpha) * (1.0 - node.energy / max(node.initial_energy, 1e-9)))

    def _neighbors(self, node: SensorNode,
                    alive: List[SensorNode]) -> List[SensorNode]:
        tx = self.params["tx_range"]
        return [n for n in alive
                if n.node_id != node.node_id
                and node.distance_to(n) <= tx and n.alive]

    def select_cluster_heads(self, alive, rnd, bs):
        if not alive: return [], {}
        self._validate_params(alive, bs)        # ← 자동 검증 실행
        n_src = min(self.params["sources_per_round"], len(alive))
        sources = self._rng.sample(alive, n_src)
        ch_ids = [s.node_id for s in sources]
        return ch_ids, {n.node_id: n.node_id for n in alive}

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, rnd) -> int:
        if not ch_ids or not alive_nodes: return 0
        node_map = {n.node_id: n for n in alive_nodes}
        pkt = self.comm.packet_size
        bs_x, bs_y = bs.x, bs.y
        tx_range = self.params["tx_range"]
        d_max = max(n.distance_to_point(bs_x, bs_y) for n in alive_nodes) or 1.0
        pkts = 0

        for src_id in ch_ids:
            src = node_map.get(src_id)
            if not src or not src.alive: continue
            current = src
            for _ in range(25):
                if not current.alive: break
                d_bs = current.distance_to_point(bs_x, bs_y)
                if d_bs <= tx_range:
                    if self._consume(current, self.em.tx_energy(pkt, d_bs)):
                        pkts += 1
                    break
                nbrs = self._neighbors(current, alive_nodes)
                closer = [n for n in nbrs
                          if n.distance_to_point(bs_x, bs_y) < d_bs]
                if closer:
                    nxt = min(closer,
                              key=lambda n: self._adjusted_cost(n, bs, d_max))
                else:
                    if not nbrs: break
                    nxt = min(nbrs,
                              key=lambda n: self._adjusted_cost(n, bs, d_max))
                    if nxt.distance_to_point(bs_x, bs_y) >= d_bs: break
                if not self._consume(current,
                                     self.em.tx_energy(pkt,
                                                       current.distance_to(nxt))):
                    break
                self._consume(nxt, self.em.rx_energy(pkt))
                current = nxt
        return pkts
