"""Export experiment results to CSV / JSON / LaTeX."""
from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Dict

import pandas as pd

from wsn_framework.core.result import AggregatedResult
from wsn_framework.experiment.metrics import Comparator

log = logging.getLogger(__name__)


class ResultExporter:
    def __init__(self, output_dir: str | Path):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)

    def export_summary_csv(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "summary.csv",
    ) -> Path:
        comp = Comparator(comparison)
        df   = comp.summary_dataframe()
        path = self.out / filename
        df.to_csv(path)
        log.info(f"Summary CSV → {path}")
        return path

    def export_summary_json(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "summary.json",
    ) -> Path:
        data = {}
        for proto, agg in comparison.items():
            data[proto] = {
                "fnd_mean": agg.fnd_mean, "fnd_std":  agg.fnd_std,
                "hnd_mean": agg.hnd_mean, "hnd_std":  agg.hnd_std,
                "lnd_mean": agg.lnd_mean,
                "pdr_mean": agg.pdr_mean, "pdr_std":  agg.pdr_std,
                "e_consumed_mean": agg.e_consumed_mean,
                "e_balance_var":   agg.e_bal_mean,
                "avg_ch_count":    agg.avg_ch_mean,
                "repetitions":     agg.repetitions,
            }
        path = self.out / filename
        path.write_text(json.dumps(data, indent=2))
        log.info(f"Summary JSON → {path}")
        return path

    def export_latex_table(
        self,
        comparison: Dict[str, AggregatedResult],
        filename: str = "results_table.tex",
    ) -> Path:
        comp  = Comparator(comparison)
        df    = comp.summary_dataframe()
        latex = df.to_latex(
            float_format="%.2f",
            bold_rows=True,
            caption="WSN Protocol Comparison Results",
            label="tab:wsn_comparison",
        )
        path = self.out / filename
        path.write_text(latex)
        log.info(f"LaTeX table → {path}")
        return path

    def export_per_round_csv(
        self,
        comparison: Dict[str, AggregatedResult],
        metric: str = "alive",   # alive | energy | packets
    ) -> Path:
        from wsn_framework.experiment.metrics import MetricsCollector
        dfs = []
        for proto, agg in comparison.items():
            if metric == "alive":
                df = MetricsCollector.alive_series(agg.raw)
                df["protocol"] = proto
            elif metric == "energy":
                df = MetricsCollector.energy_series(agg.raw)
                df["protocol"] = proto
            elif metric == "packets":
                df = MetricsCollector.packets_series(agg.raw)
                df["protocol"] = proto
            else:
                raise ValueError(f"Unknown metric '{metric}'")
            dfs.append(df)
        combined = pd.concat(dfs, ignore_index=True)
        path = self.out / f"per_round_{metric}.csv"
        combined.to_csv(path, index=False)
        log.info(f"Per-round {metric} CSV → {path}")
        return path

    def export_ttest(
        self,
        comparison: Dict[str, AggregatedResult],
        metric: str = "fnd",
    ) -> Path:
        comp = Comparator(comparison)
        df   = comp.pairwise_ttest(metric)
        path = self.out / f"ttest_{metric}.csv"
        df.to_csv(path)
        log.info(f"t-test table ({metric}) → {path}")
        return path
