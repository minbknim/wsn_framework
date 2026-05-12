"""ResultExporter — 계층형 결과 저장 (run_dir / protocol / *.csv|json|tex)."""
from __future__ import annotations
import csv, json
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
from wsn_framework.core.result import AggregatedResult, ExperimentResult


class ResultExporter:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def _proto_dir(self, protocol_name: str) -> Path:
        safe = protocol_name.replace("+", "plus").replace("-", "_")
        d = self.run_dir / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_per_round_csv(self, protocol_name: str,
                           results: List[ExperimentResult],
                           proto_dir: Optional[Path] = None) -> Path:
        if proto_dir is None:
            proto_dir = self._proto_dir(protocol_name)
        out = proto_dir / "per_round.csv"
        if not results:
            return out
        max_rnd = max((r.round_stats[-1].round_num for r in results if r.round_stats), default=0)
        if max_rnd == 0:
            return out
        alive_s = np.zeros(max_rnd + 1)
        energy_s = np.zeros(max_rnd + 1)
        ch_s = np.zeros(max_rnd + 1)
        cnt = np.zeros(max_rnd + 1)
        for res in results:
            for s in res.round_stats:
                r = s.round_num
                if r <= max_rnd:
                    alive_s[r] += s.alive_nodes
                    energy_s[r] += s.total_energy
                    ch_s[r] += s.ch_count
                    cnt[r] += 1
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["round", "alive_mean", "total_energy_mean", "ch_count_mean"])
            for r in range(1, max_rnd + 1):
                c = cnt[r]
                if c > 0:
                    w.writerow([r, round(alive_s[r]/c, 3),
                                round(energy_s[r]/c, 6), round(ch_s[r]/c, 3)])
        return out

    def save_comparison_csv(self, comparison: Dict[str, AggregatedResult]) -> Path:
        out = self.run_dir / "comparison_summary.csv"
        fields = ["protocol","repetitions","fnd_mean","fnd_std","hnd_mean","hnd_std",
                  "lnd_mean","lnd_std","pdr_mean","pdr_std","e_consumed_mean",
                  "e_bal_mean","avg_ch_mean"]
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for proto, agg in comparison.items():
                w.writerow({"protocol": agg.protocol, "repetitions": agg.repetitions,
                    "fnd_mean": round(agg.fnd_mean,2), "fnd_std": round(agg.fnd_std,2),
                    "hnd_mean": round(agg.hnd_mean,2), "hnd_std": round(agg.hnd_std,2),
                    "lnd_mean": round(agg.lnd_mean,2), "lnd_std": round(agg.lnd_std,2),
                    "pdr_mean": round(agg.pdr_mean,5), "pdr_std": round(agg.pdr_std,5),
                    "e_consumed_mean": round(agg.e_consumed_mean,4),
                    "e_bal_mean": round(agg.e_bal_mean,6),
                    "avg_ch_mean": round(agg.avg_ch_mean,3)})
        return out

    def save_comparison_json(self, comparison: Dict[str, AggregatedResult]) -> Path:
        out = self.run_dir / "comparison_summary.json"
        data = {proto: {"repetitions": agg.repetitions,
            "fnd_mean": agg.fnd_mean, "fnd_std": agg.fnd_std,
            "hnd_mean": agg.hnd_mean, "hnd_std": agg.hnd_std,
            "lnd_mean": agg.lnd_mean, "lnd_std": agg.lnd_std,
            "pdr_mean": agg.pdr_mean, "pdr_std": agg.pdr_std,
            "e_consumed": agg.e_consumed_mean,
            "e_balance": agg.e_bal_mean, "avg_ch": agg.avg_ch_mean}
            for proto, agg in comparison.items()}
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out

    def save_latex_table(self, comparison: Dict[str, AggregatedResult]) -> Path:
        out = self.run_dir / "results_table.tex"
        lines = [r"\begin{table}[h]", r"\centering",
                 r"\caption{WSN 11 Protocol Comparison}",
                 r"\label{tab:wsn_comparison}",
                 r"\begin{tabular}{lrrrrrrr}", r"\toprule",
                 r"Protocol & FND & HND & LND & PDR(\%) & E(J) & E-Bal$\times 10^{-3}$ & CH \\",
                 r"\midrule"]
        for proto, agg in comparison.items():
            lines.append(
                rf"\textbf{{{agg.protocol}}} & "
                rf"{agg.fnd_mean:.1f}$\pm${agg.fnd_std:.1f} & "
                rf"{agg.hnd_mean:.1f}$\pm${agg.hnd_std:.1f} & "
                rf"{agg.lnd_mean:.1f} & "
                rf"{agg.pdr_mean*100:.2f} & "
                rf"{agg.e_consumed_mean:.2f} & "
                rf"{agg.e_bal_mean*1000:.3f} & "
                rf"{agg.avg_ch_mean:.2f} \\")
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return out

    def export_all(self, comparison: Dict[str, AggregatedResult]) -> Dict[str, Path]:
        saved = {}
        saved["csv"]   = self.save_comparison_csv(comparison)
        saved["json"]  = self.save_comparison_json(comparison)
        saved["latex"] = self.save_latex_table(comparison)
        for proto, agg in comparison.items():
            raw = getattr(agg, "raw", [])
            if raw:
                p = self.save_per_round_csv(proto, raw)
                saved[f"per_round_{proto}"] = p
        return saved
