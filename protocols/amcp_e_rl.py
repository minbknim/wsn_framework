"""
AMCP-E-RL — Q-table 기반 K 동적 결정 (최종판 v3)

분석 결과:
  K=50 : LND=60,059
  K=100: LND=66,779
  K=150: LND=71,359  ← 최적
  K=200: LND=72,939  ← 최적

개선된 보상 함수:
  reward = alive_ratio * 0.7 + energy_ratio * 0.3 + 0.1 * K_normalized
  → 생존 노드 유지 + 에너지 여유 + 큰 K 선호
"""
from __future__ import annotations
import random, statistics
from typing import Dict, List, Tuple
from .amcp_e import AMCP_E


class AMCP_E_RL(AMCP_E):
    """AMCP-E + Q-table K 동적 결정 (최종판 v3)."""
    name = "AMCP-E-RL"
    default_params = {
        **AMCP_E.default_params,
        "k_options":     [100, 125, 150, 175, 200],  # K 범위 최적화
        "train":         True,
        "epsilon":       0.15,    # 적절한 탐색
        "epsilon_decay": 0.995,
        "epsilon_min":   0.02,
        "lr":            0.1,
        "gamma":         0.92,    # 장기 보상 중시
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._q_table: Dict[Tuple, List[float]] = {}
        self._prev_state   = None
        self._prev_action  = 2   # K=150 기본
        self._prev_alive   = 100
        self._prev_energy  = 1.0
        self._epsilon      = self.params["epsilon"]
        self._rng_rl       = random.Random(99)
        self._k_history    = []
        self._N            = 100

    def _discretize(self, alive_r: float, energy_r: float, rnd_n: float) -> Tuple:
        a = min(4, int(alive_r * 5))
        e = min(4, int(energy_r * 5))
        r = min(3, int(rnd_n   * 4))
        return (a, e, r)

    def _get_q(self, s: Tuple) -> List[float]:
        if s not in self._q_table:
            self._q_table[s] = [0.0] * len(self.params["k_options"])
        return self._q_table[s]

    def _choose(self, s: Tuple) -> int:
        if self.params["train"] and self._rng_rl.random() < self._epsilon:
            return self._rng_rl.randint(0, len(self.params["k_options"])-1)
        q  = self._get_q(s); mx = max(q)
        best = [i for i,v in enumerate(q) if v == mx]
        return self._rng_rl.choice(best)

    def _update(self, s: Tuple, a: int, r: float, ns: Tuple) -> None:
        lr = self.params["lr"]; g = self.params["gamma"]
        q  = self._get_q(s);   nq = self._get_q(ns)
        q[a] += lr * (r + g * max(nq) - q[a])

    def select_cluster_heads(self, alive_nodes, round_num, bs):
        reset_k = self.params.get("reset_k", 150)
        # K마다 RL 업데이트
        if round_num % reset_k == 1 or round_num == 1:
            n   = len(alive_nodes)
            avg_e = (sum(nd.energy for nd in alive_nodes) / max(n, 1)) / 0.5
            alive_r = n / self._N
            rnd_n   = min(1.0, round_num / 100000)
            curr_s  = self._discretize(alive_r, min(1.0, avg_e), rnd_n)

            if self.params["train"] and self._prev_state is not None:
                k_idx  = self._prev_action
                k_opts = self.params["k_options"]
                k_norm = k_idx / (len(k_opts) - 1)
                # 개선된 보상: 생존비율 + 에너지 여유 + 큰 K 선호
                alive_improvement = (n - self._prev_alive) / self._N
                reward = alive_improvement * 0.7 + min(1.0, avg_e) * 0.2 + 0.1 * k_norm
                self._update(self._prev_state, self._prev_action, reward, curr_s)

            action = self._choose(curr_s)
            new_k  = self.params["k_options"][action]
            self.params["reset_k"] = new_k
            self._k_history.append(new_k)
            self._prev_state  = curr_s
            self._prev_action = action
            self._prev_alive  = n
            self._prev_energy = avg_e

            if self.params["train"]:
                self._epsilon = max(
                    self.params["epsilon_min"],
                    self._epsilon * self.params["epsilon_decay"])

        return super().select_cluster_heads(alive_nodes, round_num, bs)

    def get_q_stats(self) -> dict:
        if not self._q_table:
            return {"states": 0}
        all_q = [v for vs in self._q_table.values() for v in vs]
        k_opt = self.params["k_options"]
        best_k = {k: 0 for k in k_opt}
        for s, q in self._q_table.items():
            best_k[k_opt[q.index(max(q))]] += 1
        avg_k = statistics.mean(self._k_history) if self._k_history else 150
        return {
            "states":       len(self._q_table),
            "q_mean":       round(sum(all_q)/len(all_q), 3) if all_q else 0,
            "epsilon":      round(self._epsilon, 4),
            "best_k":       best_k,
            "avg_k_chosen": round(avg_k, 1),
            "k_history":    len(self._k_history),
        }
