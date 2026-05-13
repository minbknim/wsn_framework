"""
topology.py — WSN 토폴로지 관리 (최종판 v3)

추가:
  - MobilityModel: RandomWaypoint 이동성 모델
  - TopologyManager.step_mobility(): 이동성 라운드 업데이트
  - GAF를 위한 이동성 지원
"""
from __future__ import annotations
import math, random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class SensorNode:
    node_id:        int
    x:              float
    y:              float
    initial_energy: float
    energy:         float     = field(init=False)
    alive:          bool      = field(init=False, default=True)

    def __post_init__(self):
        self.energy = self.initial_energy

    def distance_to(self, other: "SensorNode") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def distance_to_point(self, px: float, py: float) -> float:
        return math.hypot(self.x - px, self.y - py)


@dataclass
class BaseStation:
    x: float
    y: float


class MobilityModel:
    """
    Random Waypoint 이동성 모델 (GAF 논문 Xu et al. 2001 기반).

    Parameters
    ----------
    area_size   : 배포 영역 크기 (m)
    speed_max   : 최대 이동 속도 (m/round)
    pause_rounds: 목적지 도달 후 대기 라운드
    seed        : 난수 시드
    """
    def __init__(self, area_size: float = 100.0,
                 speed_max: float = 2.0,
                 pause_rounds: int = 10,
                 seed: int = 42):
        self.area      = area_size
        self.v_max     = speed_max
        self.pause     = pause_rounds
        self._rng      = random.Random(seed)
        # 노드별 이동 상태: {node_id: (dest_x, dest_y, speed, pause_count)}
        self._state:   Dict[int, Tuple[float, float, float, int]] = {}

    def _new_waypoint(self) -> Tuple[float, float, float]:
        """새 목적지·속도 생성."""
        dx = self._rng.uniform(0, self.area)
        dy = self._rng.uniform(0, self.area)
        v  = self._rng.uniform(0.5, self.v_max)
        return dx, dy, v

    def step(self, nodes: List[SensorNode]) -> None:
        """한 라운드 이동 업데이트."""
        for node in nodes:
            if not node.alive:
                continue
            nid = node.node_id
            if nid not in self._state:
                dx, dy, v = self._new_waypoint()
                self._state[nid] = (dx, dy, v, 0)

            dest_x, dest_y, speed, pause = self._state[nid]

            if pause > 0:
                self._state[nid] = (dest_x, dest_y, speed, pause - 1)
                continue

            dist = math.hypot(dest_x - node.x, dest_y - node.y)
            if dist <= speed:
                # 목적지 도달
                node.x = dest_x
                node.y = dest_y
                dx, dy, v = self._new_waypoint()
                self._state[nid] = (dx, dy, v, self.pause)
            else:
                # 목적지 방향으로 speed만큼 이동
                ratio   = speed / dist
                node.x += (dest_x - node.x) * ratio
                node.y += (dest_y - node.y) * ratio
                node.x  = max(0.0, min(self.area, node.x))
                node.y  = max(0.0, min(self.area, node.y))
                self._state[nid] = (dest_x, dest_y, speed, 0)


class TopologyManager:
    """WSN 토폴로지 생성 및 관리."""

    def __init__(self, cfg, energy_cfg, seed: int = 42,
                 mobility: Optional[MobilityModel] = None):
        self.cfg         = cfg
        self.energy_cfg  = energy_cfg
        self.seed        = seed
        self.nodes:      List[SensorNode] = []
        self.bs:         BaseStation      = BaseStation(x=50.0, y=50.0)
        self.mobility    = mobility          # ← 이동성 모델 (선택)
        self._rng        = random.Random(seed)

        # 설정값 안전 추출
        self.area_size   = getattr(cfg, "area_size",  100.0)
        self.num_nodes   = getattr(cfg, "num_nodes",  100)
        bs_pos           = getattr(cfg, "bs_position", None)
        if bs_pos:
            self.bs = BaseStation(x=bs_pos[0], y=bs_pos[1])

    def deploy(self) -> None:
        """노드를 영역 내 무작위 배포."""
        self.nodes = []
        E0 = self.energy_cfg.initial_energy
        for i in range(self.num_nodes):
            x = self._rng.uniform(0, self.area_size)
            y = self._rng.uniform(0, self.area_size)
            self.nodes.append(SensorNode(
                node_id=i, x=x, y=y, initial_energy=E0))

    def step_mobility(self) -> None:
        """이동성 모델이 있으면 한 라운드 이동."""
        if self.mobility is not None:
            self.mobility.step(self.nodes)

    def alive_nodes(self) -> List[SensorNode]:
        return [n for n in self.nodes if n.alive]

    def total_energy(self) -> float:
        return sum(n.energy for n in self.nodes)

    def energy_consumed(self) -> float:
        return sum(n.initial_energy - n.energy for n in self.nodes)
