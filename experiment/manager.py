"""ExperimentManager — runs, aggregates, and compares experiments."""
from __future__ import annotations
import copy, logging, sys
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np

from wsn_framework.core.config import ScenarioConfig
from wsn_framework.core.topology import TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.core.result import ExperimentResult, AggregatedResult
from wsn_framework.protocols.builtin import get_protocol

log = logging.getLogger(__name__)


def _progress(label: str, done: int, total: int) -> None:
    pct = int(done / total * 40)
    bar = "█" * pct + "░" * (40 - pct)
    sys.stdout.write(f"\r  {label:10s} [{bar}] {done}/{total}")
    sys.stdout.flush()
    if done == total:
        sys.stdout.write("\n")


class ExperimentManager:
    def __init__(self, base_config: ScenarioConfig, output_dir: str = "results"):
        self.base_cfg   = base_config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Single run ────────────────────────────────────────────────────────────

    def run_single(
        self,
        protocol_name: str,
        seed: int,
        rep_id: int = 0,
        save_topology_fig: bool = True,
    ) -> ExperimentResult:
        cfg = self.base_cfg.clone_for_protocol(protocol_name)
        cfg.simulation.seed = seed

        topo = TopologyManager(cfg.topology, cfg.energy, seed=seed)
        topo.deploy()

        if save_topology_fig and rep_id == 0:
            fig_path = (
                self.output_dir / "figures" /
                f"topology_{protocol_name}_seed{seed}.png"
            )
            topo.visualize(fig_path, title=f"Initial topology — {protocol_name}")

        em    = EnergyModel(cfg.energy)
        PCls  = get_protocol(protocol_name)
        proto = PCls(cfg.protocol, em, cfg.comm)

        result = proto.run(topo, cfg.simulation.rounds, seed, rep_id)
        return result

    # ── Monte Carlo ───────────────────────────────────────────────────────────

    def run_monte_carlo(
        self,
        protocol_name: str,
        repetitions:   Optional[int] = None,
        save_topology_fig: bool = True,
    ) -> AggregatedResult:
        reps      = repetitions or self.base_cfg.simulation.repetitions
        base_seed = self.base_cfg.simulation.seed
        results: List[ExperimentResult] = []

        log.info(f"[{protocol_name}] Monte Carlo ×{reps}")
        for rep in range(reps):
            _progress(protocol_name, rep, reps)
            seed = base_seed + rep
            r = self.run_single(
                protocol_name, seed, rep_id=rep,
                save_topology_fig=(save_topology_fig and rep == 0)
            )
            results.append(r)
        _progress(protocol_name, reps, reps)

        return self._aggregate(protocol_name, results)

    # ── Multi-protocol comparison ─────────────────────────────────────────────

    def compare(
        self,
        protocols:         List[str],
        repetitions:       Optional[int] = None,
        save_topology_fig: bool = True,
    ) -> Dict[str, AggregatedResult]:
        comparison: Dict[str, AggregatedResult] = {}
        for proto in protocols:
            agg = self.run_monte_carlo(
                proto, repetitions, save_topology_fig=save_topology_fig
            )
            comparison[proto] = agg
            log.info(
                f"  {proto:10s}  FND={agg.fnd_mean:.0f}±{agg.fnd_std:.0f}  "
                f"HND={agg.hnd_mean:.0f}±{agg.hnd_std:.0f}  "
                f"PDR={agg.pdr_mean:.3f}"
            )
        self._save_comparison_topology(protocols, save_topology_fig)
        return comparison

    # ── Aggregation ───────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(name: str, results: List[ExperimentResult]) -> AggregatedResult:
        def m(attr): return float(np.mean([getattr(r, attr) for r in results]))
        def s(attr): return float(np.std([getattr(r, attr)  for r in results]))
        agg = AggregatedResult(protocol=name, repetitions=len(results), raw=results)
        for attr in ("fnd", "hnd", "lnd"):
            setattr(agg, f"{attr}_mean", m(attr))
            setattr(agg, f"{attr}_std",  s(attr))
        agg.pdr_mean         = m("pdr");                agg.pdr_std   = s("pdr")
        agg.e_bal_mean       = m("energy_balance_var"); agg.e_bal_std = s("energy_balance_var")
        agg.e_consumed_mean  = m("total_energy_consumed")
        agg.avg_ch_mean      = m("avg_ch_count")
        return agg

    # ── Shared topology overlay ───────────────────────────────────────────────

    def _save_comparison_topology(self, protocols: List[str], save: bool) -> None:
        if not save:
            return
        seed = self.base_cfg.simulation.seed
        cfg  = self.base_cfg
        topo = TopologyManager(cfg.topology, cfg.energy, seed=seed)
        topo.deploy()
        fig_path = self.output_dir / "figures" / f"topology_shared_seed{seed}.png"
        topo.visualize(
            fig_path,
            title=f"Shared topology (seed={seed})  |  {', '.join(protocols)}",
        )
        log.info(f"Shared topology → {fig_path}")
