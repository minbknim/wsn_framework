"""LEACH-C — LEACH Centralized.

Heinzelman, W. B., Chandrakasan, A. P., & Balakrishnan, H. (2002).
An application-specific protocol architecture for wireless microsensor networks.
IEEE Trans. Wireless Communications, 1(4), 660–670.

BS가 전체 노드 에너지를 수집하여 최적 CH를 선출 (중앙집중식).
평균 이상 에너지를 가진 노드 중 최적 분포로 CH 선정.
"""
from __future__ import annotations
import math
import random
from typing import List, Dict, Tuple

from .base import BaseProtocol
from wsn_framework.core.topology import SensorNode, BaseStation


class LEACH_C(BaseProtocol):
    """BS 중앙집중 CH 선출: 평균 에너지 이상 노드 중 simulated annealing 분산 최적화."""
    name = "LEACH-C"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)

    def _optimal_ch_selection(
        self, candidates: List[SensorNode], k: int
    ) -> List[int]:
        """에너지 가중 거리 최소화 기반 CH 선정 (greedy approximation)."""
        if not candidates or k <= 0:
            return []
        if k >= len(candidates):
            return [n.node_id for n in candidates]

        # 에너지 가중 greedy: 에너지 높고 분산이 좋은 노드 선택
        selected: List[SensorNode] = []
        remaining = list(candidates)
        # 첫 번째: 가장 에너지 높은 노드
        best = max(remaining, key=lambda n: n.energy)
        selected.append(best)
        remaining.remove(best)

        while len(selected) < k and remaining:
            # 기존 선택된 CH들과의 최소거리 최대화 (spread 극대화)
            best = max(remaining, key=lambda n: (
                min(n.distance_to(s) for s in selected) * n.energy
            ))
            selected.append(best)
            remaining.remove(best)

        return [n.node_id for n in selected]

    def select_cluster_heads(
        self, alive_nodes: List[SensorNode], round_num: int, bs: BaseStation
    ) -> Tuple[List[int], Dict[int, int]]:
        if not alive_nodes:
            return [], {}

        avg_energy = sum(n.energy for n in alive_nodes) / len(alive_nodes)
        # BS가 에너지 정보 수집 → 평균 이상 노드만 후보
        candidates = [n for n in alive_nodes if n.energy >= avg_energy]
        if not candidates:
            candidates = alive_nodes[:]

        k = max(1, round(self.cfg.ch_ratio * len(alive_nodes)))
        ch_ids = self._optimal_ch_selection(candidates, k)

        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        from .leach import LEACH
        return LEACH.run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num)
