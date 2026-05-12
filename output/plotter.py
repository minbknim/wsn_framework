"""Plotter — 11개 프로토콜 비교 그래프 생성."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from wsn_framework.core.result import AggregatedResult
from wsn_framework.experiment.metrics import MetricsCollector, Comparator

log = logging.getLogger(__name__)

# 11개 프로토콜을 위한 팔레트
PALETTE = sns.color_palette("tab20", 20)
STYLE = {
    "figure.facecolor": "white",
    "axes.facecolor":   "#f8f9fa",
    "axes.grid":        True,
    "grid.alpha":       0.4,
    "grid.linewidth":   0.5,
    "font.size":        10,
}


class Plotter:
    def __init__(self, output_dir: str | Path):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        plt.rcParams.update(STYLE)

    def _save(self, fig, filename: str) -> Path:
        p = self.out / filename
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return p

    # ── 생존 노드 ────────────────────────────────────────────────────────────

    def plot_alive_nodes(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "alive_nodes.png",
    ) -> Path:
        fig, ax = plt.subplots(figsize=(12, 6))
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.alive_series(agg.raw)
            ax.plot(df["round"], df["alive_mean"],
                    label=proto, color=PALETTE[i % 20], linewidth=1.6)
            ax.fill_between(df["round"],
                            df["alive_mean"] - df["alive_std"],
                            df["alive_mean"] + df["alive_std"],
                            alpha=0.10, color=PALETTE[i % 20])
        ax.set_xlabel("Round"); ax.set_ylabel("Alive nodes")
        ax.set_title("Network Lifetime — Alive Nodes per Round")
        ax.legend(fontsize=8, ncol=3)
        return self._save(fig, filename)

    # ── 잔여 에너지 ──────────────────────────────────────────────────────────

    def plot_energy(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "energy_consumption.png",
    ) -> Path:
        fig, ax = plt.subplots(figsize=(12, 6))
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.energy_series(agg.raw)
            ax.plot(df["round"], df["energy_mean"],
                    label=proto, color=PALETTE[i % 20], linewidth=1.6)
        ax.set_xlabel("Round"); ax.set_ylabel("Total residual energy (J)")
        ax.set_title("Residual Energy per Round")
        ax.legend(fontsize=8, ncol=3)
        return self._save(fig, filename)

    # ── FND/HND/LND 막대 ─────────────────────────────────────────────────────

    def plot_lifetime_bars(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "lifetime_bars.png",
    ) -> Path:
        protos = list(comparison.keys())
        metrics = [("FND","fnd_mean","fnd_std"),
                   ("HND","hnd_mean","hnd_std"),
                   ("LND","lnd_mean","lnd_std")]
        x = np.arange(len(protos))
        w = 0.26
        fig, ax = plt.subplots(figsize=(max(12, len(protos)*1.2), 6))
        for j, (label, m, s) in enumerate(metrics):
            vals = [getattr(comparison[p], m) for p in protos]
            errs = [getattr(comparison[p], s) for p in protos]
            ax.bar(x + j*w, vals, w, yerr=errs, label=label,
                   color=PALETTE[j], alpha=0.85, capsize=3)
        ax.set_xticks(x + w); ax.set_xticklabels(protos, rotation=30, ha="right")
        ax.set_ylabel("Round"); ax.set_title("Network Lifetime (FND / HND / LND)")
        ax.legend(fontsize=9)
        return self._save(fig, filename)

    # ── LND 전용 수평 막대 (전체 수명 비교) ──────────────────────────────────

    def plot_lnd_comparison(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "lnd_comparison.png",
    ) -> Path:
        protos = list(comparison.keys())
        lnds  = [comparison[p].lnd_mean for p in protos]
        stds  = [comparison[p].lnd_std  for p in protos]
        fig, ax = plt.subplots(figsize=(9, max(4, len(protos)*0.6)))
        y = np.arange(len(protos))
        bars = ax.barh(y, lnds, xerr=stds, color=PALETTE[:len(protos)],
                       alpha=0.85, capsize=4)
        ax.set_yticks(y); ax.set_yticklabels(protos)
        ax.set_xlabel("Last Node Dead (rounds)")
        ax.set_title("Network Sustainability (LND) Comparison")
        for bar, v, sd in zip(bars, lnds, stds):
            ax.text(v + sd + 5, bar.get_y() + bar.get_height()/2,
                    f"{v:.0f}", va="center", fontsize=8)
        return self._save(fig, filename)

    # ── PDR 비교 ─────────────────────────────────────────────────────────────

    def plot_pdr(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "pdr_comparison.png",
    ) -> Path:
        protos = list(comparison.keys())
        vals   = [comparison[p].pdr_mean for p in protos]
        errs   = [comparison[p].pdr_std  for p in protos]
        fig, ax = plt.subplots(figsize=(max(10, len(protos)*0.9), 5))
        bars = ax.bar(protos, vals, yerr=errs,
                      color=PALETTE[:len(protos)], alpha=0.85, capsize=4)
        ax.set_ylabel("PDR"); ax.set_title("Packet Delivery Ratio")
        ax.tick_params(axis="x", rotation=30)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.001, f"{v:.4f}",
                    ha="center", fontsize=8)
        return self._save(fig, filename)

    # ── 에너지 균형 ──────────────────────────────────────────────────────────

    def plot_energy_balance(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "energy_balance.png",
    ) -> Path:
        protos = list(comparison.keys())
        vals   = [comparison[p].e_bal_mean * 1000 for p in protos]
        fig, ax = plt.subplots(figsize=(max(10, len(protos)*0.9), 5))
        bars = ax.bar(protos, vals, color=PALETTE[:len(protos)], alpha=0.85)
        ax.set_ylabel("Energy Balance Variance (×10⁻³)")
        ax.set_title("Energy Balance (lower = more uniform)")
        ax.tick_params(axis="x", rotation=30)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.01, f"{v:.3f}",
                    ha="center", fontsize=8)
        return self._save(fig, filename)

    # ── t-test 히트맵 ─────────────────────────────────────────────────────────

    def plot_ttest_heatmap(
        self,
        comparison: Dict[str, AggregatedResult],
        metric: str = "lnd",
        filename: str = "ttest_heatmap.png",
    ) -> Path:
        c = Comparator(comparison)
        pmat = c.pairwise_ttest(metric)
        protos = list(pmat.index)
        fig, ax = plt.subplots(figsize=(max(7, len(protos)*0.8), max(5, len(protos)*0.6)))
        sns.heatmap(pmat.astype(float), annot=True, fmt=".3f",
                    cmap="RdYlGn", ax=ax, vmin=0, vmax=0.1,
                    linewidths=0.5, annot_kws={"size": 7})
        ax.set_title(f"Welch t-test p-value ({metric.upper()})")
        return self._save(fig, filename)

    # ── 종합 대시보드 ─────────────────────────────────────────────────────────

    def plot_dashboard(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "dashboard.png",
    ) -> Path:
        fig = plt.figure(figsize=(18, 12))
        gs  = fig.add_gridspec(2, 3, hspace=0.4, wspace=0.35)

        # 1) Alive nodes
        ax1 = fig.add_subplot(gs[0, :2])
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.alive_series(agg.raw)
            ax1.plot(df["round"], df["alive_mean"],
                     label=proto, color=PALETTE[i % 20], linewidth=1.4)
        ax1.set_xlabel("Round"); ax1.set_ylabel("Alive nodes")
        ax1.set_title("Alive Nodes per Round")
        ax1.legend(fontsize=7, ncol=4)

        # 2) LND 막대
        ax2 = fig.add_subplot(gs[0, 2])
        protos = list(comparison.keys())
        lnds = [comparison[p].lnd_mean for p in protos]
        y = np.arange(len(protos))
        ax2.barh(y, lnds, color=PALETTE[:len(protos)], alpha=0.8)
        ax2.set_yticks(y); ax2.set_yticklabels(protos, fontsize=7)
        ax2.set_xlabel("LND (rounds)"); ax2.set_title("Last Node Dead")

        # 3) FND/HND/LND
        ax3 = fig.add_subplot(gs[1, 0])
        x = np.arange(len(protos)); w = 0.25
        for j, (lbl, attr) in enumerate([("FND","fnd_mean"),("HND","hnd_mean"),("LND","lnd_mean")]):
            ax3.bar(x+j*w, [getattr(comparison[p], attr) for p in protos],
                    w, label=lbl, color=PALETTE[j], alpha=0.85)
        ax3.set_xticks(x+w); ax3.set_xticklabels(protos, rotation=30, ha="right", fontsize=7)
        ax3.set_ylabel("Round"); ax3.set_title("FND/HND/LND"); ax3.legend(fontsize=7)

        # 4) PDR
        ax4 = fig.add_subplot(gs[1, 1])
        pdrs = [comparison[p].pdr_mean for p in protos]
        ax4.bar(protos, pdrs, color=PALETTE[:len(protos)], alpha=0.85)
        ax4.set_ylabel("PDR"); ax4.set_title("Packet Delivery Ratio")
        ax4.tick_params(axis="x", rotation=30, labelsize=7)

        # 5) E-balance
        ax5 = fig.add_subplot(gs[1, 2])
        ebs = [comparison[p].e_bal_mean*1000 for p in protos]
        ax5.bar(protos, ebs, color=PALETTE[:len(protos)], alpha=0.85)
        ax5.set_ylabel("Var ×10⁻³"); ax5.set_title("Energy Balance")
        ax5.tick_params(axis="x", rotation=30, labelsize=7)

        return self._save(fig, filename)

    # ── 전체 출력 ─────────────────────────────────────────────────────────────

    def plot_all(self, comparison: Dict[str, AggregatedResult]) -> List[Path]:
        figs = []
        figs.append(self.plot_alive_nodes(comparison))
        figs.append(self.plot_energy(comparison))
        figs.append(self.plot_lifetime_bars(comparison))
        figs.append(self.plot_lnd_comparison(comparison))
        figs.append(self.plot_pdr(comparison))
        figs.append(self.plot_energy_balance(comparison))
        try:
            figs.append(self.plot_ttest_heatmap(comparison, "lnd"))
        except Exception:
            pass
        figs.append(self.plot_dashboard(comparison))
        return figs
