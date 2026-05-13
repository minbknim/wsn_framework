"""
metrics.py — 실험 결과 통계 분석 (최종판 v2)

추가:
  - pairwise_ttest(): 16개 프로토콜 간 Welch t-검정 행렬 자동 생성
  - effect_size(): Cohen's d 효과 크기
  - bootstrap_ci(): 부트스트랩 신뢰구간
"""
from __future__ import annotations
import math, statistics
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from wsn_framework.core.result import AggregatedResult, ExperimentResult


def aggregate(results: List[ExperimentResult]) -> AggregatedResult:
    """ExperimentResult 리스트 → AggregatedResult 집계."""
    if not results:
        raise ValueError("빈 결과 리스트")

    def _mean(vals): return statistics.mean(vals) if vals else 0.0
    def _std(vals):  return statistics.stdev(vals) if len(vals) > 1 else 0.0

    fnds = [r.fnd for r in results]
    hnds = [r.hnd for r in results]
    lnds = [r.lnd for r in results]
    pdrs = [r.pdr for r in results]
    ebals = [r.energy_balance_var for r in results]
    econs = [r.total_energy_consumed for r in results]
    chs   = [r.avg_ch_count for r in results]

    agg = AggregatedResult(
        protocol=results[0].protocol,
        repetitions=len(results),
    )
    agg.fnd_mean = _mean(fnds);  agg.fnd_std = _std(fnds)
    agg.hnd_mean = _mean(hnds);  agg.hnd_std = _std(hnds)
    agg.lnd_mean = _mean(lnds);  agg.lnd_std = _std(lnds)
    agg.pdr_mean = _mean(pdrs);  agg.pdr_std = _std(pdrs)
    agg.e_bal_mean = _mean(ebals); agg.e_bal_std = _std(ebals)
    agg.e_consumed_mean = _mean(econs)
    agg.avg_ch_mean = _mean(chs)
    agg.raw = results
    return agg


def cohens_d(a: List[float], b: List[float]) -> float:
    """Cohen's d 효과 크기 계산."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa, sb = statistics.stdev(a), statistics.stdev(b)
    na, nb = len(a), len(b)
    pooled = math.sqrt(((na-1)*sa**2 + (nb-1)*sb**2) / (na+nb-2))
    return (ma - mb) / pooled if pooled > 0 else 0.0


def welch_ttest(a: List[float], b: List[float]) -> Tuple[float, float]:
    """Welch t-검정 (등분산 불가정). 반환: (t_stat, p_value 근사)"""
    if len(a) < 2 or len(b) < 2:
        return 0.0, 1.0
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa2, sb2 = statistics.variance(a), statistics.variance(b)
    na, nb  = len(a), len(b)
    se = math.sqrt(sa2/na + sb2/nb)
    if se == 0:
        return 0.0, 1.0 if ma == mb else (float("inf"), 0.0)
    t = (ma - mb) / se
    # Welch-Satterthwaite 자유도
    df_num = (sa2/na + sb2/nb)**2
    df_den = (sa2/na)**2/(na-1) + (sb2/nb)**2/(nb-1)
    df = df_num / df_den if df_den > 0 else 1.0
    # p값 근사 (t분포 CDF — 정규분포 근사)
    p = 2 * (1 - _normal_cdf(abs(t))) if df > 30 else _t_cdf_approx(abs(t), df)
    return t, p


def _normal_cdf(x: float) -> float:
    """표준 정규분포 CDF 근사."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def _t_cdf_approx(t: float, df: float) -> float:
    """t분포 단측 CDF 근사 (df>1)."""
    x = df / (df + t*t)
    # 불완전 베타함수 근사
    a, b = df/2, 0.5
    # 간단한 수치 근사
    p_one = 0.5 * _incomplete_beta(x, a, b)
    return 1.0 - p_one


def _incomplete_beta(x, a, b, iterations=100):
    """불완전 베타함수 수치 근사 (연분수 전개)."""
    if x < 0 or x > 1:
        return 0.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a*math.log(x+1e-300) + b*math.log(1-x+1e-300) - lbeta) / a
    cf = 1.0
    for m in range(1, iterations):
        d = m*(b-m)*x / ((a+2*m-1)*(a+2*m))
        cf = 1 + d / (1 + (-(a+m)*(a+b+m)*x / ((a+2*m)*(a+2*m+1))) / cf)
    return front * cf


def pairwise_ttest(
    results_dict: Dict[str, AggregatedResult],
    metric: str = "lnd",
    alpha: float = 0.05,
) -> Dict[Tuple[str,str], Dict]:
    """
    16개 프로토콜 간 Welch t-검정 자동 행렬 생성.

    Parameters
    ----------
    results_dict : {protocol_name: AggregatedResult}
    metric       : 'lnd', 'fnd', 'hnd', 'pdr' 중 선택
    alpha        : 유의수준 (기본 0.05)

    Returns
    -------
    {(p1, p2): {'t': float, 'p': float, 'd': float, 'sig': bool,
                'm1': float, 'm2': float}}
    """
    results: Dict[Tuple[str,str], Dict] = {}

    # raw LND 리스트 추출
    raw_vals: Dict[str, List[float]] = {}
    for pname, agg in results_dict.items():
        vals = [getattr(r, metric) for r in agg.raw
                if hasattr(r, metric)]
        if vals:
            raw_vals[pname] = vals

    protocols = sorted(raw_vals.keys())
    for p1, p2 in combinations(protocols, 2):
        a = raw_vals[p1]
        b = raw_vals[p2]
        t_stat, p_val = welch_ttest(a, b)
        d = cohens_d(a, b)
        results[(p1, p2)] = {
            "t":   round(t_stat, 3),
            "p":   round(p_val, 4),
            "d":   round(d, 3),
            "sig": p_val < alpha,
            "m1":  round(statistics.mean(a), 1),
            "m2":  round(statistics.mean(b), 1),
        }
    return results


def bootstrap_ci(
    values: List[float],
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """부트스트랩 신뢰구간."""
    import random
    rng = random.Random(seed)
    n   = len(values)
    boot_means = []
    for _ in range(n_boot):
        sample = [rng.choice(values) for _ in range(n)]
        boot_means.append(statistics.mean(sample))
    boot_means.sort()
    lo = int((1 - ci) / 2 * n_boot)
    hi = int((1 + ci) / 2 * n_boot)
    return boot_means[lo], boot_means[min(hi, n_boot-1)]


# ── 하위 호환성 aliases ────────────────────────────────────────────────────────
class MetricsCollector:
    """하위 호환성 유지 — aggregate() 함수를 클래스 형태로 제공."""
    @staticmethod
    def collect(results):
        return aggregate(results)


class Comparator:
    """하위 호환성 유지 — pairwise_ttest() 함수를 클래스 형태로 제공."""
    @staticmethod
    def compare(results_dict, metric="lnd", alpha=0.05):
        return pairwise_ttest(results_dict, metric, alpha)
