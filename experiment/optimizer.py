"""
optimizer.py — 프로토콜 파라미터 자동 최적화 (Bayesian / Grid Search)

구현 항목:
  - SEP m_frac 최적화: m_frac∈[0.05,0.3] 탐색 → σ 최소화
  - 범용 파라미터 탐색: Grid Search (optuna 미설치 환경 대응)
  - 결과: 최적 파라미터 + LND/σ 비교표
"""
from __future__ import annotations
import random, time, statistics as st
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from wsn_framework.core.config import ScenarioConfig
from wsn_framework.core.topology import TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.protocols import get_protocol


def _run_n_seeds(
    proto_name: str,
    params: Dict[str, Any],
    cfg: ScenarioConfig,
    em: EnergyModel,
    n_seeds: int = 10,
    base_seed: int = 42,
    metric: str = "lnd",
) -> Tuple[float, float]:
    """n_seeds 회 실험 후 (mean, std) 반환."""
    vals: List[float] = []
    for seed in range(base_seed, base_seed + n_seeds):
        topo = TopologyManager(cfg.topology, cfg.energy, seed=seed)
        topo.deploy()
        proto = get_protocol(proto_name)(cfg.protocol, em, cfg.comm)
        for k, v in params.items():
            proto.params[k] = v
        r = proto.run(topo, 1_000_000, seed, 0, run_until_dead=True)
        vals.append(getattr(r, metric))
    mean = st.mean(vals)
    std  = st.stdev(vals) if len(vals) > 1 else 0.0
    return mean, std


def optimize_sep_m_frac(
    cfg: ScenarioConfig,
    em: EnergyModel,
    m_frac_range: Tuple[float, float] = (0.05, 0.35),
    n_steps: int = 6,
    n_seeds: int = 10,
    target: str = "min_sigma",   # 'min_sigma' | 'max_lnd' | 'balanced'
) -> Dict:
    """
    SEP m_frac 파라미터 최적화.

    Parameters
    ----------
    target : 'min_sigma'  → σ 최소화
             'max_lnd'    → LND 평균 최대화
             'balanced'   → LND/σ 비율 최대화

    Returns
    -------
    {best_m_frac, best_mean, best_std, results_table}
    """
    lo, hi = m_frac_range
    step   = (hi - lo) / (n_steps - 1)
    candidates = [round(lo + i * step, 3) for i in range(n_steps)]

    table: List[Dict] = []
    best_score = None
    best_m     = candidates[0]
    best_mean  = 0.0
    best_std   = float("inf")

    print(f"  SEP m_frac 최적화 시작 (n_steps={n_steps}, seeds={n_seeds})")
    for m in candidates:
        t0 = time.time()
        mean, std = _run_n_seeds(
            "SEP", {"m_frac": m, "alpha": 1.0}, cfg, em, n_seeds=n_seeds)
        elapsed = time.time() - t0

        if target == "min_sigma":
            score = -std          # σ 최소
        elif target == "max_lnd":
            score = mean          # 평균 최대
        else:
            score = mean / max(std, 1.0)  # LND/σ 최대

        table.append({"m_frac": m, "mean": mean, "std": std,
                      "score": score, "elapsed": elapsed})
        print(f"    m_frac={m:.3f}: LND={mean:,.0f}  σ={std:,.0f}  score={score:.2f}  ({elapsed:.1f}s)")

        if best_score is None or score > best_score:
            best_score = score
            best_m     = m
            best_mean  = mean
            best_std   = std

    return {
        "best_m_frac": best_m,
        "best_mean":   best_mean,
        "best_std":    best_std,
        "target":      target,
        "table":       table,
    }


def grid_search(
    proto_name: str,
    param_grids: Dict[str, List],
    cfg: ScenarioConfig,
    em: EnergyModel,
    n_seeds: int = 5,
    metric: str = "lnd",
    objective: str = "max_mean",  # 'max_mean' | 'min_std' | 'balanced'
) -> Dict:
    """
    범용 Grid Search 파라미터 최적화.

    Parameters
    ----------
    param_grids : {param_name: [v1, v2, v3, ...]}

    Returns
    -------
    {best_params, best_mean, best_std, all_results}
    """
    import itertools

    param_names  = list(param_grids.keys())
    param_values = list(param_grids.values())
    combos = list(itertools.product(*param_values))

    print(f"  {proto_name} grid search: {len(combos)}개 조합, {n_seeds} seeds")

    all_results = []
    best_score  = None
    best_params = {}
    best_mean   = 0.0
    best_std    = float("inf")

    for combo in combos:
        params = dict(zip(param_names, combo))
        mean, std = _run_n_seeds(proto_name, params, cfg, em, n_seeds=n_seeds,
                                  metric=metric)
        if objective == "max_mean":
            score = mean
        elif objective == "min_std":
            score = -std
        else:
            score = mean / max(std, 1.0)

        all_results.append({**params, "mean": mean, "std": std, "score": score})
        print(f"    {params}  → {metric}={mean:,.0f}  σ={std:,.0f}")

        if best_score is None or score > best_score:
            best_score  = score
            best_params = params
            best_mean   = mean
            best_std    = std

    return {
        "best_params": best_params,
        "best_mean":   best_mean,
        "best_std":    best_std,
        "all_results": sorted(all_results, key=lambda x: -x["score"]),
    }
