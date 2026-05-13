"""
mobility.py — 이동성 노드 모델 (잔존문제 2: GAF 이동성 지원)

구현 모델:
  - RandomWaypointMobility: 랜덤 웨이포인트 (이동→정지→이동)
  - StaticMobility: 기본값 (이동 없음)
  - TopologyManager와 통합: step() 호출로 라운드마다 이동
"""
from __future__ import annotations
import random, math
from typing import List, Optional, Tuple
from wsn_framework.core.topology import SensorNode


class MobilityModel:
    """이동성 모델 기반 클래스."""
    def step(self, nodes: List[SensorNode], round_num: int,
             area_size: float = 100.0) -> None:
        pass

    @staticmethod
    def clamp(val: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, val))


class StaticMobility(MobilityModel):
    """정적 노드 (이동 없음) — 기본값."""
    pass


class RandomWaypointMobility(MobilityModel):
    """
    Random Waypoint Mobility Model.

    각 노드는:
    1. 랜덤 목표 지점(waypoint)을 선택
    2. 속도 v∈[v_min, v_max] m/round로 이동
    3. 목표 도달 시 pause_time 라운드 정지
    4. 다음 waypoint 선택 반복

    GAF 논문 (Xu et al. 2001)의 이동성 시나리오 구현.
    """
    def __init__(
        self,
        v_min: float = 0.5,     # 최소 속도 (m/round)
        v_max: float = 2.0,     # 최대 속도 (m/round)
        pause_min: int = 0,     # 최소 정지 시간 (rounds)
        pause_max: int = 10,    # 최대 정지 시간 (rounds)
        seed: int = 42,
    ):
        self.v_min     = v_min
        self.v_max     = v_max
        self.pause_min = pause_min
        self.pause_max = pause_max
        self._rng      = random.Random(seed)

        # 노드별 상태
        self._target:    dict = {}   # node_id → (tx, ty)
        self._velocity:  dict = {}   # node_id → (vx, vy)
        self._pause_rem: dict = {}   # node_id → pause 남은 라운드

    def _init_node(self, node: SensorNode, area: float) -> None:
        """노드 초기 waypoint 설정."""
        tx = self._rng.uniform(0, area)
        ty = self._rng.uniform(0, area)
        v  = self._rng.uniform(self.v_min, self.v_max)
        dx = tx - node.x
        dy = ty - node.y
        dist = math.sqrt(dx**2 + dy**2) or 1.0
        self._target[node.node_id]    = (tx, ty)
        self._velocity[node.node_id]  = (v * dx / dist, v * dy / dist)
        self._pause_rem[node.node_id] = 0

    def step(self, nodes: List[SensorNode], round_num: int,
             area_size: float = 100.0) -> None:
        """한 라운드 이동 처리."""
        for node in nodes:
            if not node.alive:
                continue
            nid = node.node_id

            # 초기화
            if nid not in self._target:
                self._init_node(node, area_size)

            # 정지 중
            if self._pause_rem.get(nid, 0) > 0:
                self._pause_rem[nid] -= 1
                continue

            # 이동
            vx, vy = self._velocity.get(nid, (0.0, 0.0))
            node.x = self.clamp(node.x + vx, 0, area_size)
            node.y = self.clamp(node.y + vy, 0, area_size)

            # 목표 도달 여부 확인
            tx, ty = self._target.get(nid, (node.x, node.y))
            if math.sqrt((node.x - tx)**2 + (node.y - ty)**2) < 1.0:
                # 정지 후 다음 waypoint
                self._pause_rem[nid] = self._rng.randint(self.pause_min, self.pause_max)
                self._init_node(node, area_size)


class GaussMarkovMobility(MobilityModel):
    """
    Gauss-Markov Mobility Model — 더 부드러운 이동 궤적.

    속도와 방향이 이전 값에 의존하여 관성을 가짐.
    α=0: 완전 랜덤 / α=1: 직선 이동
    """
    def __init__(
        self,
        alpha: float = 0.75,   # 메모리 계수 (0~1)
        v_mean: float = 1.0,   # 평균 속도 (m/round)
        v_std:  float = 0.3,   # 속도 표준편차
        seed: int = 42,
    ):
        self.alpha  = alpha
        self.v_mean = v_mean
        self.v_std  = v_std
        self._rng   = random.Random(seed)
        self._vx: dict = {}   # node_id → vx
        self._vy: dict = {}   # node_id → vy

    def step(self, nodes: List[SensorNode], round_num: int,
             area_size: float = 100.0) -> None:
        for node in nodes:
            if not node.alive: continue
            nid = node.node_id
            prev_vx = self._vx.get(nid, self._rng.gauss(0, self.v_std))
            prev_vy = self._vy.get(nid, self._rng.gauss(0, self.v_std))

            alpha = self.alpha
            eta = math.sqrt(1 - alpha**2)
            new_vx = (alpha * prev_vx
                      + (1-alpha) * self.v_mean
                      + eta * self._rng.gauss(0, self.v_std))
            new_vy = (alpha * prev_vy
                      + (1-alpha) * self.v_mean
                      + eta * self._rng.gauss(0, self.v_std))

            node.x = self.clamp(node.x + new_vx, 0, area_size)
            node.y = self.clamp(node.y + new_vy, 0, area_size)

            # 경계 반사
            if node.x <= 0 or node.x >= area_size: new_vx = -new_vx
            if node.y <= 0 or node.y >= area_size: new_vy = -new_vy

            self._vx[nid] = new_vx
            self._vy[nid] = new_vy


def create_mobility(model_name: str = "static", **kwargs) -> MobilityModel:
    """이동성 모델 팩토리."""
    models = {
        "static":        StaticMobility,
        "random_waypoint": RandomWaypointMobility,
        "gauss_markov":  GaussMarkovMobility,
    }
    cls = models.get(model_name.lower(), StaticMobility)
    return cls(**kwargs)
