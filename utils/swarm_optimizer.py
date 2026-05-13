"""
swarm_optimizer.py — PSO 기반 WSN 노드 위치 최적화

Swarm Optimization (개선방안 차후연구 항목 구현)
Kennedy & Eberhart (1995) PSO 알고리즘 기반

목적: 초기 노드 배포 위치를 최적화하여 에너지 균형 향상
     → FND/LND 개선 효과
"""
from __future__ import annotations
import math, random
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Particle:
    """PSO 입자 — 노드 위치 집합을 표현."""
    positions:  List[Tuple[float,float]]   # [(x0,y0), (x1,y1), ...]
    velocities: List[Tuple[float,float]]
    best_pos:   List[Tuple[float,float]]
    best_score: float = float('inf')


class PSOOptimizer:
    """
    PSO 기반 WSN 노드 배포 위치 최적화.

    목적함수: 에너지 균형 지표 최소화
      = Σ|d(i,BS) - d_avg| / N   (BS 거리 분산 최소화)

    Parameters
    ----------
    n_nodes   : 노드 수
    area_size : 배포 영역 크기 (m)
    bs_pos    : BS 위치 (x, y)
    n_particles: PSO 입자 수
    n_iter    : 반복 횟수
    w         : 관성 가중치
    c1, c2    : 인지·사회 계수
    """

    def __init__(self,
                 n_nodes:    int   = 100,
                 area_size:  float = 100.0,
                 bs_pos:     Tuple = (50.0, 50.0),
                 n_particles:int   = 20,
                 n_iter:     int   = 50,
                 w:          float = 0.7,
                 c1:         float = 1.5,
                 c2:         float = 1.5,
                 seed:       int   = 42):
        self.n_nodes    = n_nodes
        self.area       = area_size
        self.bs         = bs_pos
        self.n_p        = n_particles
        self.n_iter     = n_iter
        self.w          = w
        self.c1         = c1
        self.c2         = c2
        self._rng       = random.Random(seed)
        self.best_global: List[Tuple[float,float]] = []
        self.best_g_score: float = float('inf')
        self.history:   List[float] = []

    def _rand_positions(self) -> List[Tuple[float,float]]:
        return [(self._rng.uniform(0, self.area),
                 self._rng.uniform(0, self.area))
                for _ in range(self.n_nodes)]

    def _rand_velocities(self) -> List[Tuple[float,float]]:
        v_max = self.area * 0.1
        return [(self._rng.uniform(-v_max, v_max),
                 self._rng.uniform(-v_max, v_max))
                for _ in range(self.n_nodes)]

    def _objective(self, positions: List[Tuple[float,float]]) -> float:
        """목적함수: BS 거리 분산 최소화."""
        bx, by = self.bs
        dists = [math.hypot(x-bx, y-by) for x,y in positions]
        d_avg = sum(dists) / len(dists)
        variance = sum((d-d_avg)**2 for d in dists) / len(dists)
        # 추가: 노드 간 최소거리 패널티 (너무 밀집 방지)
        min_dist_penalty = 0.0
        for i in range(min(len(positions), 20)):   # 계산 절약
            for j in range(i+1, min(len(positions), 20)):
                d = math.hypot(positions[i][0]-positions[j][0],
                               positions[i][1]-positions[j][1])
                if d < 5.0:
                    min_dist_penalty += (5.0 - d)
        return math.sqrt(variance) + min_dist_penalty * 0.1

    def optimize(self) -> List[Tuple[float,float]]:
        """PSO 최적화 실행. 최적 노드 위치 반환."""
        # 초기화
        particles = []
        for _ in range(self.n_p):
            pos = self._rand_positions()
            vel = self._rand_velocities()
            p   = Particle(positions=pos, velocities=vel,
                           best_pos=list(pos))
            p.best_score = self._objective(pos)
            particles.append(p)
            if p.best_score < self.best_g_score:
                self.best_g_score = p.best_score
                self.best_global  = list(pos)

        # PSO 반복
        for it in range(self.n_iter):
            for p in particles:
                new_pos = []; new_vel = []
                for i, ((px,py),(vx,vy)) in enumerate(
                        zip(p.positions, p.velocities)):
                    bpx, bpy = p.best_pos[i]
                    gpx, gpy = self.best_global[i]
                    r1 = self._rng.random(); r2 = self._rng.random()
                    nvx = (self.w * vx
                           + self.c1*r1*(bpx-px)
                           + self.c2*r2*(gpx-px))
                    nvy = (self.w * vy
                           + self.c1*r1*(bpy-py)
                           + self.c2*r2*(gpy-py))
                    # 속도 제한
                    v_max = self.area * 0.1
                    nvx = max(-v_max, min(v_max, nvx))
                    nvy = max(-v_max, min(v_max, nvy))
                    npx = max(0, min(self.area, px+nvx))
                    npy = max(0, min(self.area, py+nvy))
                    new_vel.append((nvx, nvy))
                    new_pos.append((npx, npy))

                p.positions  = new_pos
                p.velocities = new_vel
                score = self._objective(new_pos)
                if score < p.best_score:
                    p.best_score = score
                    p.best_pos   = list(new_pos)
                if score < self.best_g_score:
                    self.best_g_score = score
                    self.best_global  = list(new_pos)

            self.history.append(self.best_g_score)

        return self.best_global

    def compare_random_vs_pso(self, n_trials: int = 5) -> dict:
        """랜덤 배포 vs PSO 최적화 비교."""
        random_scores = []
        for _ in range(n_trials):
            pos = self._rand_positions()
            random_scores.append(self._objective(pos))

        pso_pos   = self.optimize()
        pso_score = self._objective(pso_pos)

        return {
            "random_mean":  sum(random_scores)/len(random_scores),
            "random_std":   (sum((s-sum(random_scores)/len(random_scores))**2
                                 for s in random_scores)/len(random_scores))**0.5,
            "pso_score":    pso_score,
            "improvement":  (sum(random_scores)/len(random_scores) - pso_score)
                            / (sum(random_scores)/len(random_scores)) * 100,
            "history":      self.history,
        }
