"""Plotter — generate all comparison and per-round figures."""
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

PALETTE = sns.color_palette("Set2", 8)
STYLE   = {
    "figure.facecolor": "white",
    "axes.facecolor":   "#f8f9fa",
    "axes.grid":        True,
    "grid.alpha":       0.4,
    "grid.linewidth":   0.5,
    "font.size":        11,
}


class Plotter:
    def __init__(self, output_dir: str | Path):
        self.out = Path(output_dir) / "figures"
        self.out.mkdir(parents=True, exist_ok=True)
        plt.rcParams.update(STYLE)

    # ── Alive nodes over rounds ───────────────────────────────────────────────

    def plot_alive_nodes(
        self,
        comparison: Dict[str, AggregatedResult],
        filename:   str = "alive_nodes.png",
    ) -> Path:
        fig, ax = plt.subplots(figsize=(9, 5))
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.alive_series(agg.raw)
            ax.plot(df["round"], df["alive_mean"],
                    label=proto, color=PALETTE[i % 8], linewidth=1.8)
            ax.fill_between(
                df["round"],
                df["alive_mean"] - df["alive_std"],
                df["alive_mean"] + df["alive_std"],
                alpha=0.15, color=PALETTE[i % 8]
            )
        ax.set_xlabel("Round"); ax.set_ylabel("Alive nodes")
        ax.set_title("Network lifetime — alive nodes per round")
        ax.legend(fontsize=9)
        return self._save(fig, filename)

    # ── Total energy over rounds ──────────────────────────────────────────────

    def plot_energy(
        self,
        comparison: Dict[str, AggregatedResult],
        filename:   str = "energy_consumption.png",
    ) -> Path:
        fig, ax = plt.subplots(figsize=(9, 5))
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.energy_series(agg.raw)
            ax.plot(df["round"], df["energy_mean"],
                    label=proto, color=PALETTE[i % 8], linewidth=1.8)
        ax.set_xlabel("Round"); ax.set_ylabel("Total residual energy (J)")
        ax.set_title("Residual energy per round")
        ax.legend(fontsize=9)
        return self._save(fig, filename)

    # ── FND / HND / LND bar chart ─────────────────────────────────────────────

    def plot_lifetime_bars(
        self,
        comparison: Dict[str, AggregatedResult],
        filename:   str = "lifetime_bars.png",
    ) -> Path:
        protos = list(comparison.keys())
        metrics = ["FND", "HND", "LND"]
        x = np.arange(len(protos))
        w = 0.25
        fig, ax = plt.subplots(figsize=(9, 5))
        for j, (mname, attr) in enumerate(
            zip(metrics, ["fnd_mean", "hnd_mean", "lnd_mean"])
        ):
            vals = [getattr(comparison[p], attr) for p in protos]
            errs = [getattr(comparison[p], attr.replace("mean", "std"))
                    for p in protos]
            ax.bar(x + j * w, vals, w, yerr=errs, label=mname,
                   color=PALETTE[j], alpha=0.85, capsize=3)
        ax.set_xticks(x + w); ax.set_xticklabels(protos, fontsize=10)
        ax.set_ylabel("Round"); ax.set_title("Network lifetime (FND / HND / LND)")
        ax.legend(fontsize=9)
        return self._save(fig, filename)

    # ── PDR comparison ────────────────────────────────────────────────────────

    def plot_pdr(
        self,
        comparison: Dict[str, AggregatedResult],
        filename:   str = "pdr_comparison.png",
    ) -> Path:
        protos = list(comparison.keys())
        vals   = [comparison[p].pdr_mean   for p in protos]
        errs   = [comparison[p].pdr_std    for p in protos]
        fig, ax = plt.subplots(figsize=(7, 4))
        bars = ax.bar(protos, vals, yerr=errs, color=PALETTE[:len(protos)],
                      alpha=0.85, capsize=4)
        ax.set_ylabel("PDR"); ax.set_title("Packet Delivery Ratio")
        ax.set_ylim(0, min(1.05, max(vals) * 1.2))
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=8)
        return self._save(fig, filename)

    # ── Energy balance heatmap ────────────────────────────────────────────────

    def plot_energy_balance(
        self,
        comparison: Dict[str, AggregatedResult],
        filename:   str = "energy_balance.png",
    ) -> Path:
        protos = list(comparison.keys())
        vals   = [comparison[p].e_bal_mean for p in protos]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(protos, vals, color=PALETTE[:len(protos)], alpha=0.85)
        ax.set_ylabel("Energy balance variance (J²)")
        ax.set_title("Energy distribution uniformity (lower = better)")
        return self._save(fig, filename)

    # ── t-test p-value heatmap ────────────────────────────────────────────────

    def plot_ttest_heatmap(
        self,
        comparison: Dict[str, AggregatedResult],
        metric:     str = "fnd",
        filename:   str = "ttest_heatmap.png",
    ) -> Path:
        comp = Comparator(comparison)
        pval = comp.pairwise_ttest(metric).astype(float)
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(pval, annot=True, fmt=".3f", cmap="YlOrRd_r",
                    vmin=0, vmax=0.1, ax=ax, linewidths=0.5,
                    annot_kws={"size": 9})
        ax.set_title(f"Pairwise Welch t-test p-values  [{metric.upper()}]")
        return self._save(fig, filename)

    # ── Summary dashboard ─────────────────────────────────────────────────────

    def plot_dashboard(
        self,
        comparison: Dict[str, AggregatedResult],
        filename:   str = "dashboard.png",
    ) -> Path:
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle("WSN Protocol Comparison Dashboard",
                     fontsize=14, fontweight="bold", y=0.98)

        # Alive nodes
        ax1 = fig.add_subplot(2, 3, 1)
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.alive_series(agg.raw)
            ax1.plot(df["round"], df["alive_mean"],
                     label=proto, color=PALETTE[i % 8], linewidth=1.5)
        ax1.set_title("Alive nodes"); ax1.set_xlabel("Round")
        ax1.legend(fontsize=7)

        # Energy
        ax2 = fig.add_subplot(2, 3, 2)
        for i, (proto, agg) in enumerate(comparison.items()):
            df = MetricsCollector.energy_series(agg.raw)
            ax2.plot(df["round"], df["energy_mean"],
                     label=proto, color=PALETTE[i % 8], linewidth=1.5)
        ax2.set_title("Residual energy (J)"); ax2.set_xlabel("Round")

        # FND/HND bars
        ax3 = fig.add_subplot(2, 3, 3)
        protos = list(comparison.keys())
        x = np.arange(len(protos))
        ax3.bar(x - 0.2, [comparison[p].fnd_mean for p in protos], 0.4,
                label="FND", color=PALETTE[0], alpha=0.85)
        ax3.bar(x + 0.2, [comparison[p].hnd_mean for p in protos], 0.4,
                label="HND", color=PALETTE[1], alpha=0.85)
        ax3.set_xticks(x); ax3.set_xticklabels(protos, fontsize=8)
        ax3.set_title("FND / HND"); ax3.legend(fontsize=7)

        # PDR
        ax4 = fig.add_subplot(2, 3, 4)
        ax4.bar(protos, [comparison[p].pdr_mean for p in protos],
                color=PALETTE[:len(protos)], alpha=0.85)
        ax4.set_title("PDR"); ax4.set_ylim(0, 1.05)

        # Energy balance
        ax5 = fig.add_subplot(2, 3, 5)
        ax5.bar(protos, [comparison[p].e_bal_mean for p in protos],
                color=PALETTE[:len(protos)], alpha=0.85)
        ax5.set_title("Energy balance variance")

        # Avg CH
        ax6 = fig.add_subplot(2, 3, 6)
        ax6.bar(protos, [comparison[p].avg_ch_mean for p in protos],
                color=PALETTE[:len(protos)], alpha=0.85)
        ax6.set_title("Avg cluster heads / round")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        return self._save(fig, filename)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _save(self, fig: plt.Figure, filename: str) -> Path:
        path = self.out / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info(f"Figure saved → {path}")
        return path
