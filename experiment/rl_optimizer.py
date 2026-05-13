"""
rl_optimizer.py — 강화학습 기반 AMCP-E K 파라미터 동적 결정 (잔존문제 3)

DQN (Deep Q-Network) 대신 Q-table (tabular RL) 구현:
  - 의존성: numpy만 필요 (tensorflow/torch 불필요)
  - State: (alive_ratio_bin, energy_ratio_bin, round_phase)
  - Action: K ∈ {50, 100, 150, 200}
  - Reward: 라운드당 LND 향상 / 노드 사망 시 페널티

학습 결과: 최적 K 정책 → AMCP-E K 동적 결정
"""
from __future__ import annotations
import random, math, statistics as st
from typing import Dict, List, Tuple
from pathlib import Path


class QTable:
    """
    Q-테이블 기반 강화학습.

    State: (alive_bin, energy_bin, phase_bin) — 각 0~4
    Action: K_INDEX ∈ {0,1,2,3} → K ∈ {50,100,150,200}
    """
    K_VALUES  = [50, 100, 150, 200]
    N_STATES  = 5 * 5 * 3   # alive_bin × energy_bin × phase_bin
    N_ACTIONS = 4

    def __init__(
        self,
        lr:      float = 0.1,    # 학습률
        gamma:   float = 0.95,   # 할인율
        epsilon: float = 0.3,    # 탐색률 (ε-greedy)
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.98,
        seed: int = 42,
    ):
        self.lr           = lr
        self.gamma        = gamma
        self.epsilon      = epsilon
        self.epsilon_min  = epsilon_min
        self.epsilon_decay= epsilon_decay
        self._rng         = random.Random(seed)
        # Q 테이블 초기화 (낙관적 초기값으로 탐색 장려)
        self.Q: Dict[Tuple, List[float]] = {}

    def _state(self, alive_ratio: float, energy_ratio: float,
               round_num: int, max_rounds: int = 150000) -> Tuple:
        """연속 상태 → 이산 상태 변환."""
        alive_bin  = min(int(alive_ratio * 5), 4)
        energy_bin = min(int(energy_ratio * 5), 4)
        phase = 0 if round_num < max_rounds * 0.33 else (
                1 if round_num < max_rounds * 0.66 else 2)
        return (alive_bin, energy_bin, phase)

    def _get_q(self, state: Tuple) -> List[float]:
        if state not in self.Q:
            self.Q[state] = [1.0] * self.N_ACTIONS  # 낙관적 초기값
        return self.Q[state]

    def act(self, state: Tuple) -> int:
        """ε-greedy 행동 선택. 반환: action_index"""
        if self._rng.random() < self.epsilon:
            return self._rng.randint(0, self.N_ACTIONS - 1)
        q = self._get_q(state)
        return q.index(max(q))

    def update(self, state: Tuple, action: int, reward: float,
               next_state: Tuple, done: bool) -> None:
        """Q-값 업데이트 (Bellman)."""
        q     = self._get_q(state)
        q_nxt = self._get_q(next_state)
        target = reward + (0.0 if done else self.gamma * max(q_nxt))
        q[action] += self.lr * (target - q[action])

    def decay_epsilon(self) -> None:
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def best_k(self, alive_ratio: float, energy_ratio: float,
               round_num: int) -> int:
        """현재 상태에서 최적 K값 반환."""
        state = self._state(alive_ratio, energy_ratio, round_num)
        if state not in self.Q:
            return 100  # 기본값
        q = self.Q[state]
        return self.K_VALUES[q.index(max(q))]


def train_k_policy(
    cfg,
    em,
    n_episodes: int = 30,
    max_rounds:  int = 150_000,
    seed:        int = 42,
    verbose:     bool = True,
) -> QTable:
    """
    AMCP-E K 파라미터 최적 정책 학습.

    에피소드마다 새 토폴로지로 시뮬레이션.
    매 1000라운드마다 K 행동을 선택하고 보상을 계산.
    """
    from wsn_framework.core.topology import TopologyManager
    from wsn_framework.protocols import get_protocol

    qtable = QTable()
    episode_lnds: List[int] = []

    for ep in range(n_episodes):
        ep_seed = seed + ep
        topo    = TopologyManager(cfg.topology, cfg.energy, seed=ep_seed)
        topo.deploy()
        nodes   = topo.nodes
        bs      = topo.bs
        proto   = get_protocol("AMCP-E")(cfg.protocol, em, cfg.comm)

        total_e0  = sum(n.initial_energy for n in nodes)
        K_STEP    = 500   # K 선택 주기 (라운드)
        prev_alive = len(nodes)
        step_reward = 0.0
        lnd = 1

        curr_k   = 100
        prev_state = qtable._state(1.0, 1.0, 0, max_rounds)
        action_idx = qtable.K_VALUES.index(100)

        for rnd in range(1, max_rounds + 1):
            alive = [n for n in nodes if n.alive]
            if not alive: break
            lnd = rnd

            # K 선택 주기마다 행동 결정
            if rnd % K_STEP == 1:
                alive_ratio  = len(alive) / len(nodes)
                energy_ratio = sum(n.energy for n in alive) / total_e0
                curr_state   = qtable._state(alive_ratio, energy_ratio,
                                              rnd, max_rounds)

                # 이전 행동의 보상 계산 (생존 노드 비율)
                reward = (len(alive) / len(nodes)) * 10.0
                done   = (len(alive) == 0)
                qtable.update(prev_state, action_idx, reward,
                              curr_state, done)

                # 새 행동 선택
                action_idx = qtable.act(curr_state)
                curr_k     = QTable.K_VALUES[action_idx]
                proto.params["reset_k"] = curr_k
                prev_state = curr_state

            ch_ids, cm = proto.select_cluster_heads(alive, rnd, bs)
            proto.run_round(alive, ch_ids, cm, bs, rnd)

        episode_lnds.append(lnd)
        qtable.decay_epsilon()

        if verbose and ep % 5 == 0:
            print(f"  Episode {ep+1:3d}/{n_episodes}: LND={lnd:6d}  "
                  f"ε={qtable.epsilon:.3f}  Q-states={len(qtable.Q)}")

    if verbose:
        print(f"\n  학습 완료: 평균 LND={st.mean(episode_lnds):,.0f}  "
              f"Q-states={len(qtable.Q)}")

    return qtable


def evaluate_k_policy(
    qtable: QTable,
    cfg,
    em,
    n_eval: int = 10,
    seed:   int = 142,
) -> Dict:
    """
    학습된 K 정책 평가.
    동적 K vs 고정 K=100 비교.
    """
    from wsn_framework.core.topology import TopologyManager
    from wsn_framework.protocols import get_protocol

    dynamic_lnds: List[int] = []
    fixed_lnds:   List[int] = []

    for i in range(n_eval):
        ep_seed = seed + i

        # 동적 K (학습된 정책)
        topo = TopologyManager(cfg.topology, cfg.energy, seed=ep_seed)
        topo.deploy()
        proto = get_protocol("AMCP-E")(cfg.protocol, em, cfg.comm)
        nodes = topo.nodes
        bs    = topo.bs
        total_e0 = sum(n.initial_energy for n in nodes)
        lnd = 1
        K_STEP = 500
        for rnd in range(1, 1_000_000):
            alive = [n for n in nodes if n.alive]
            if not alive: break
            lnd = rnd
            if rnd % K_STEP == 1:
                ar = len(alive) / len(nodes)
                er = sum(n.energy for n in alive) / total_e0
                proto.params["reset_k"] = qtable.best_k(ar, er, rnd)
            ch_ids, cm = proto.select_cluster_heads(alive, rnd, bs)
            proto.run_round(alive, ch_ids, cm, bs, rnd)
        dynamic_lnds.append(lnd)

        # 고정 K=100 (기존)
        topo2 = TopologyManager(cfg.topology, cfg.energy, seed=ep_seed)
        topo2.deploy()
        proto2 = get_protocol("AMCP-E")(cfg.protocol, em, cfg.comm)
        r = proto2.run(topo2, 1_000_000, ep_seed, 0, run_until_dead=True)
        fixed_lnds.append(r.lnd)

    return {
        "dynamic_mean": st.mean(dynamic_lnds),
        "dynamic_std":  st.stdev(dynamic_lnds) if len(dynamic_lnds)>1 else 0,
        "fixed_mean":   st.mean(fixed_lnds),
        "fixed_std":    st.stdev(fixed_lnds) if len(fixed_lnds)>1 else 0,
        "improvement":  (st.mean(dynamic_lnds)/st.mean(fixed_lnds)-1)*100,
    }
