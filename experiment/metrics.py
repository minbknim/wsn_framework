"""Metrics collection and statistical comparison between protocols."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from wsn_framework.core.result import AggregatedResult, ExperimentResult

log = logging.getLogger(__name__)


class MetricsCollector:
    """Extract per-round time-series from raw results."""

    @staticmethod
    def alive_series(results: List[ExperimentResult]) -> pd.DataFrame:
        """Mean alive nodes per round across repetitions."""
        max_rnd = max(len(r.round_stats) for r in results)
        data: Dict[int, List[int]] = {i: [] for i in range(1, max_rnd + 1)}
        for r in results:
            for rs in r.round_stats:
                data[rs.round_num].append(rs.alive_nodes)
        rows = [
            {"round": rnd, "alive_mean": np.mean(vs), "alive_std": np.std(vs)}
            for rnd, vs in data.items() if vs
        ]
        return pd.DataFrame(rows)

    @staticmethod
    def energy_series(results: List[ExperimentResult]) -> pd.DataFrame:
        """Mean total energy per round across repetitions."""
        max_rnd = max(len(r.round_stats) for r in results)
        data: Dict[int, List[float]] = {i: [] for i in range(1, max_rnd + 1)}
        for r in results:
            for rs in r.round_stats:
                data[rs.round_num].append(rs.total_energy)
        rows = [
            {"round": rnd, "energy_mean": np.mean(vs), "energy_std": np.std(vs)}
            for rnd, vs in data.items() if vs
        ]
        return pd.DataFrame(rows)

    @staticmethod
    def packets_series(results: List[ExperimentResult]) -> pd.DataFrame:
        max_rnd = max(len(r.round_stats) for r in results)
        data: Dict[int, List[int]] = {i: [] for i in range(1, max_rnd + 1)}
        for r in results:
            for rs in r.round_stats:
                data[rs.round_num].append(rs.packets_to_bs)
        rows = [
            {"round": rnd, "packets_mean": np.mean(vs)}
            for rnd, vs in data.items() if vs
        ]
        return pd.DataFrame(rows)


class Comparator:
    """Statistical comparison of protocol results."""

    def __init__(self, comparison: Dict[str, AggregatedResult]):
        self.comparison = comparison

    def summary_dataframe(self) -> pd.DataFrame:
        rows = []
        for proto, agg in self.comparison.items():
            rows.append({
                "Protocol":      proto,
                "FND mean":      round(agg.fnd_mean, 1),
                "FND std":       round(agg.fnd_std, 1),
                "HND mean":      round(agg.hnd_mean, 1),
                "HND std":       round(agg.hnd_std, 1),
                "LND mean":      round(agg.lnd_mean, 1),
                "PDR mean":      round(agg.pdr_mean, 4),
                "PDR std":       round(agg.pdr_std, 4),
                "E consumed (J)": round(agg.e_consumed_mean, 4),
                "E balance var": round(agg.e_bal_mean, 6),
                "Avg CH count":  round(agg.avg_ch_mean, 2),
            })
        df = pd.DataFrame(rows).set_index("Protocol")
        return df

    def pairwise_ttest(
        self, metric: str = "fnd"
    ) -> pd.DataFrame:
        """Pairwise Welch t-test for a given metric across all protocol pairs."""
        protocols = list(self.comparison.keys())
        pvals = pd.DataFrame(index=protocols, columns=protocols, dtype=float)
        for a in protocols:
            for b in protocols:
                if a == b:
                    pvals.loc[a, b] = 1.0
                    continue
                va = [getattr(r, metric) for r in self.comparison[a].raw]
                vb = [getattr(r, metric) for r in self.comparison[b].raw]
                _, p = stats.ttest_ind(va, vb, equal_var=False)
                pvals.loc[a, b] = round(p, 4)
        return pvals

    def rank(self, metric: str = "fnd_mean", ascending: bool = False) -> pd.DataFrame:
        df = self.summary_dataframe().reset_index()
        col_map = {
            "fnd_mean": "FND mean", "hnd_mean": "HND mean",
            "pdr_mean": "PDR mean", "e_consumed_mean": "E consumed (J)",
        }
        col = col_map.get(metric, metric)
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not in summary. Available: {list(df.columns)}")
        return df.sort_values(col, ascending=ascending).reset_index(drop=True)
