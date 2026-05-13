"""
SPIN — Sensor Protocols for Information via Negotiation (SPIN-PP 변형)

Kulik, J., Heinzelman, W. B., & Balakrishnan, H. (2002).
Negotiation-based protocols for disseminating information in wireless sensor networks.
Wireless Networks, 8(2-3), 169–185. DOI:10.1023/A:1013715909417

핵심 알고리즘 (SPIN-PP 기반):
  1. 데이터 보유 노드가 이웃에게 ADV(광고) 메시지 브로드캐스트
  2. 아직 해당 데이터를 받지 못한 이웃이 REQ(요청) 전송
  3. 원본 노드가 DATA 패킷 전송
  4. 수신 노드가 다시 ADV 브로드캐스트 반복 (플러딩 없이 전파)

에너지 모델 (First-order 적용):
  - ADV/REQ: ctrl_packet_size 사용
  - DATA: packet_size 사용
  - 중복 전송 방지: 이미 데이터 보유 노드는 REQ 안 함

프레임워크 적용 단순화:
  - 각 라운드마다 임의 노드들이 데이터 수집
  - SPIN 방식으로 이웃에게 전파 (반경 내 노드)
  - 최종적으로 BS로 전달된 패킷 수 카운트
"""
from __future__ import annotations
import random
from typing import List, Dict, Tuple, Set

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class SPIN(BaseProtocol):
    """
    SPIN-PP: ADV-REQ-DATA 3단계 메타데이터 협상 기반 데이터 전파.

    WSN 시뮬레이션 적응:
    - 각 라운드: 1개 소스 노드가 데이터 감지 후 SPIN 전파 시작
    - 전파 반경: tx_range 내 이웃 노드
    - BS 범위 내 도달 시 패킷 카운트
    """
    name = "SPIN"
    default_params = {
        "tx_range": 50.0,     # 전송 반경 (m) — 이웃 탐색용
        "sources_per_round": 1,  # 라운드당 데이터 생성 노드 수
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._has_data: Set[int] = set()   # 현재 라운드에 데이터를 보유한 노드

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        """SPIN은 CH 구조가 없음 — 소스 노드를 'CH'로 표시."""
        if not alive_nodes:
            return [], {}

        # 소스 노드 무작위 선택
        n_src = min(self.params["sources_per_round"], len(alive_nodes))
        sources = self._rng.sample(alive_nodes, n_src)
        ch_ids = [s.node_id for s in sources]

        # cluster_map: 모든 노드를 자기 자신에게 (SPIN은 클러스터 없음)
        cluster_map = {n.node_id: n.node_id for n in alive_nodes}

        # 이 라운드의 초기 데이터 보유 노드
        self._has_data = set(ch_ids)
        return ch_ids, cluster_map

    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        if not ch_ids or not alive_nodes:
            return 0

        tx_range = self.params["tx_range"]
        node_map = {n.node_id: n for n in alive_nodes}
        pkt  = self.comm.packet_size
        ctrl = self.comm.ctrl_packet_size

        # SPIN 전파 시뮬레이션
        # 큐: 데이터를 방금 받은 노드 (ADV를 보낼 노드들)
        to_advertise = list(self._has_data)
        bs_x, bs_y = bs.x, bs.y
        pkts_to_bs = 0

        # 최대 홉 수 제한 (무한 루프 방지)
        max_hops = 10
        hop = 0

        while to_advertise and hop < max_hops:
            next_wave: List[int] = []

            for src_id in to_advertise:
                src = node_map.get(src_id)
                if not src or not src.alive:
                    continue

                # 이웃 탐색 (tx_range 내)
                neighbors = [
                    n for n in alive_nodes
                    if n.node_id != src_id
                    and src.distance_to(n) <= tx_range
                ]

                # ADV 브로드캐스트 (이웃 전체에게)
                for nbr in neighbors:
                    adv_cost = self.em.tx_energy(ctrl, src.distance_to(nbr))
                    src.energy -= adv_cost
                    if src.energy <= 0:
                        src.energy = 0; src.alive = False; break

                if not src.alive:
                    continue

                # 데이터 없는 이웃들이 REQ 보내고 DATA 수신
                interested = [n for n in neighbors if n.node_id not in self._has_data]

                for nbr in interested:
                    if not nbr.alive or not src.alive:
                        break

                    # REQ 전송 (nbr → src)
                    req_cost = self.em.tx_energy(ctrl, nbr.distance_to(src))
                    nbr.energy -= req_cost
                    if nbr.energy <= 0:
                        nbr.energy = 0; nbr.alive = False; continue

                    # RX REQ (src 수신)
                    rx_req = self.em.rx_energy(ctrl)
                    src.energy -= rx_req
                    if src.energy <= 0:
                        src.energy = 0; src.alive = False; break

                    # DATA 전송 (src → nbr)
                    tx_data = self.em.tx_energy(pkt, src.distance_to(nbr))
                    src.energy -= tx_data
                    if src.energy <= 0:
                        src.energy = 0; src.alive = False

                    # RX DATA (nbr 수신)
                    rx_data = self.em.rx_energy(pkt)
                    nbr.energy -= rx_data
                    if nbr.energy <= 0:
                        nbr.energy = 0; nbr.alive = False; continue

                    # nbr이 데이터를 받음
                    self._has_data.add(nbr.node_id)
                    next_wave.append(nbr.node_id)

                    # BS가 이웃이면 패킷 카운트
                    if nbr.distance_to_point(bs_x, bs_y) <= tx_range:
                        pkts_to_bs += 1

            to_advertise = next_wave
            hop += 1

        # 소스 노드가 BS 범위 내이면 직접 전송
        for src_id in ch_ids:
            src = node_map.get(src_id)
            if src and src.alive:
                d_bs = src.distance_to_point(bs_x, bs_y)
                if d_bs <= tx_range * 3:  # BS 직접 전송 가능 범위
                    tx = self.em.tx_energy(pkt, d_bs)
                    src.energy -= tx
                    if src.energy <= 0:
                        src.energy = 0; src.alive = False
                    else:
                        pkts_to_bs += 1

        self._has_data.clear()
        return min(pkts_to_bs, len(ch_ids))
