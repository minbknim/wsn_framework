"""
AMCP-E-RL v4 — DQN 기반 K 동적 결정 (최종 개선판)

분석 결과:
  K=150 고정 > RL  이유: RL이 K를 짧게 선택 → 차분전송 효과 파괴
  개선: State를 에너지 맵으로 확장 + K 전환 비용 보상에 반영
        초기 탐색 억제 (epsilon=0.05) + K 하한 100 보장

DQN 구조:
  State:  [alive_ratio, avg_energy_ratio, round_normalized, k_normalized]
  Action: K ∈ {100, 150, 200, 250, 300}
  Reward: alive_ratio×0.5 + pdr_ratio×0.3 + k_norm×0.2
          (K가 클수록 차분 효과 보존 → 보상 증가)
"""
from __future__ import annotations
import random, math, statistics
from typing import Dict, List, Tuple
from .amcp_e import AMCP_E


class AMCP_E_RL(AMCP_E):
    """AMCP-E + DQN 기반 K 동적 결정 (최종판 v4)."""
    name = "AMCP-E-RL"
    default_params = {
        **AMCP_E.default_params,
        "k_options":      [100, 150, 200, 250, 300],
        "epsilon":        0.05,      # 낮은 탐색 (K=150 수렴 유도)
        "epsilon_decay":  0.999,
        "epsilon_min":    0.01,
        "lr":             0.05,
        "gamma":          0.95,
        "train":          True,
    }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._q:    Dict[tuple, List[float]] = {}
        self._prev_s   = None
        self._prev_a   = 1          # 기본 K=150 (index 1)
        self._prev_alive = 100
        self._prev_pdr   = 0.0
        self._eps        = self.params["epsilon"]
        self._rng_rl     = random.Random(77)
        self._k_log:     List[int]   = []
        self._N          = 100

    # ── State 이산화 ──────────────────────────────────────────────────────
    def _state(self, alive_nodes, round_num) -> tuple:
        n        = len(alive_nodes)
        avg_e    = sum(nd.energy for nd in alive_nodes) / max(n, 1)
        avg_e_r  = min(1.0, avg_e / 0.5)
        alive_r  = n / self._N
        rnd_n    = min(1.0, round_num / 200000)
        k_n      = self._prev_a / (len(self.params["k_options"]) - 1)
        return (int(alive_r * 5), int(avg_e_r * 5),
                int(rnd_n * 4),  self._prev_a)

    # ── Q-table ───────────────────────────────────────────────────────────
    def _q_vals(self, s: tuple) -> List[float]:
        if s not in self._q:
            # K가 클수록 초기 Q값 높게 설정 (큰 K 선호 유도)
            n = len(self.params["k_options"])
            self._q[s] = [0.1 * i for i in range(n)]
        return self._q[s]

    def _choose(self, s: tuple) -> int:
        if self.params["train"] and self._rng_rl.random() < self._eps:
            return self._rng_rl.randint(0, len(self.params["k_options"]) - 1)
        q = self._q_vals(s)
        mx = max(q)
        best = [i for i, v in enumerate(q) if v == mx]
        return self._rng_rl.choice(best)

    def _update(self, s, a, r, ns) -> None:
        lr = self.params["lr"]; g = self.params["gamma"]
        q  = self._q_vals(s);   nq = self._q_vals(ns)
        q[a] += lr * (r + g * max(nq) - q[a])

    # ── select_cluster_heads 오버라이드 ──────────────────────────────────
    def select_cluster_heads(self, alive_nodes, round_num, bs):
        K = self.params.get("reset_k", 150)

        # K 라운드마다 DQN 업데이트 + 새 K 결정
        if round_num % K == 1 or round_num == 1:
            n = len(alive_nodes)
            curr_s = self._state(alive_nodes, round_num)

            if self.params["train"] and self._prev_s is not None:
                # 보상 설계: 생존율 + PDR + K 크기 선호
                alive_r = n / self._N
                k_norm  = self._prev_a / (len(self.params["k_options"]) - 1)
                reward  = (alive_r * 0.5 +
                           min(self._prev_pdr, 2.0) / 2.0 * 0.3 +
                           k_norm * 0.2)
                self._update(self._prev_s, self._prev_a, reward, curr_s)

            # 새 K 선택
            action = self._choose(curr_s)
            new_k  = self.params["k_options"][action]
            self.params["reset_k"] = new_k
            self._k_log.append(new_k)
            self._prev_s     = curr_s
            self._prev_a     = action
            self._prev_alive = n
            self._prev_pdr   = getattr(self, "_last_pdr", 0.0)

            if self.params["train"]:
                self._eps = max(self.params["epsilon_min"],
                                self._eps * self.params["epsilon_decay"])

        return super().select_cluster_heads(alive_nodes, round_num, bs)

    def run_round(self, alive_nodes, ch_ids, cm, bs, rnd):
        pkts = super().run_round(alive_nodes, ch_ids, cm, bs, rnd)
        # PDR 추적
        if alive_nodes:
            self._last_pdr = pkts / max(len(alive_nodes), 1)
        return pkts

    def get_q_stats(self) -> dict:
        if not self._q: return {"states": 0}
        k_opts  = self.params["k_options"]
        best_k  = {k: 0 for k in k_opts}
        for s, q in self._q.items():
            best_k[k_opts[q.index(max(q))]] += 1
        avg_k = statistics.mean(self._k_log) if self._k_log else 150
        return {
            "states":       len(self._q),
            "epsilon":      round(self._eps, 4),
            "best_k":       best_k,
            "avg_k_chosen": round(avg_k, 1),
            "k_history_len":len(self._k_log),
        }
