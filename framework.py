"""WSNFramework — top-level API."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Optional

from wsn_framework.core.config import ScenarioConfig
from wsn_framework.experiment.manager import ExperimentManager
from wsn_framework.experiment.metrics import Comparator
from wsn_framework.output.exporter import ResultExporter
from wsn_framework.output.plotter import Plotter
from wsn_framework.core.result import AggregatedResult
from wsn_framework.core.topology import TopologyManager

log = logging.getLogger(__name__)


class WSNFramework:
    """
    Single entry-point for the WSN simulation framework.

    Usage::

        fw = WSNFramework.from_yaml("configs/default_scenario.yaml",
                                    output_dir="results/exp01")
        results = fw.compare(["LEACH", "HEED", "PEGASIS", "SEP"])
        fw.export_all(results)
    """

    def __init__(self, config: ScenarioConfig, output_dir: str = "results"):
        self.config     = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._manager  = ExperimentManager(config, output_dir=str(self.output_dir))
        self._exporter = ResultExporter(self.output_dir)
        self._plotter  = Plotter(self.output_dir)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: str, output_dir: str = "results") -> "WSNFramework":
        cfg = ScenarioConfig.from_yaml(path)
        cfg.validate()
        return cls(cfg, output_dir=output_dir)

    @classmethod
    def from_defaults(cls, output_dir: str = "results") -> "WSNFramework":
        default = Path(__file__).parent / "configs" / "default_scenario.yaml"
        return cls.from_yaml(str(default), output_dir=output_dir)

    # ── Run APIs ──────────────────────────────────────────────────────────────

    def run(
        self,
        protocol:    str,
        repetitions: Optional[int] = None,
    ) -> AggregatedResult:
        """Run Monte Carlo for a single protocol."""
        log.info(f"Running {protocol} ×{repetitions or self.config.simulation.repetitions}")
        return self._manager.run_monte_carlo(protocol, repetitions)

    def compare(
        self,
        protocols:   List[str],
        repetitions: Optional[int] = None,
    ) -> Dict[str, AggregatedResult]:
        """
        Run all protocols under identical topology/energy environments.
        Returns dict {protocol_name: AggregatedResult}.
        """
        log.info(f"Comparing {protocols}")
        return self._manager.compare(protocols, repetitions)

    def sweep(
        self,
        protocols: List[str],
        param:     str,
        values:    list,
    ) -> Dict[str, Dict[str, AggregatedResult]]:
        """
        Parameter sweep: vary one config parameter across given values.
        Returns {param_value: {protocol: AggregatedResult}}.
        """
        import copy, yaml
        results: Dict[str, Dict[str, AggregatedResult]] = {}
        for val in values:
            log.info(f"Sweep {param}={val}")
            cfg_copy = copy.deepcopy(self.config)
            # Support dot-notation: e.g. "topology.num_nodes"
            parts = param.split(".")
            obj = cfg_copy
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], val)
            cfg_copy.validate()

            sub_dir = self.output_dir / f"sweep_{param}_{val}"
            sub_fw  = WSNFramework(cfg_copy, output_dir=str(sub_dir))
            results[str(val)] = sub_fw.compare(protocols)
        return results

    # ── Topology visualisation ────────────────────────────────────────────────

    def save_topology(
        self,
        output_path: Optional[str] = None,
        title:       str = "Initial WSN Topology",
    ) -> Path:
        """Render and save the initial topology figure (no simulation)."""
        topo = TopologyManager(
            self.config.topology,
            self.config.energy,
            seed=self.config.simulation.seed,
        )
        topo.deploy()
        path = output_path or str(
            self.output_dir / "figures" / "initial_topology.png"
        )
        return topo.visualize(path, title=title,
                              tx_range=self.config.comm.tx_range)

    # ── Export & plots ────────────────────────────────────────────────────────

    def export_all(self, comparison: Dict[str, AggregatedResult]) -> None:
        """Export every result artefact: CSV, JSON, LaTeX, all plots."""
        log.info("Exporting results …")
        self._exporter.export_summary_csv(comparison)
        self._exporter.export_summary_json(comparison)
        self._exporter.export_latex_table(comparison)
        self._exporter.export_per_round_csv(comparison, "alive")
        self._exporter.export_per_round_csv(comparison, "energy")
        self._exporter.export_per_round_csv(comparison, "packets")
        self._exporter.export_ttest(comparison, "fnd")
        self._exporter.export_ttest(comparison, "hnd")

        self._plotter.plot_alive_nodes(comparison)
        self._plotter.plot_energy(comparison)
        self._plotter.plot_lifetime_bars(comparison)
        self._plotter.plot_pdr(comparison)
        self._plotter.plot_energy_balance(comparison)
        self._plotter.plot_ttest_heatmap(comparison)
        self._plotter.plot_dashboard(comparison)
        log.info(f"All results saved → {self.output_dir}")

    def print_summary(self, comparison: Dict[str, AggregatedResult]) -> None:
        """Print ranked summary table to stdout."""
        from tabulate import tabulate
        comp = Comparator(comparison)
        df   = comp.summary_dataframe().reset_index()
        print("\n" + "="*70)
        print("  WSN Protocol Comparison Summary")
        print("="*70)
        print(tabulate(df, headers="keys", tablefmt="rounded_outline",
                       floatfmt=".3f", showindex=False))
        print()
        # Ranking
        ranked = comp.rank("fnd_mean", ascending=False)
        print("  Ranking by FND (higher = longer first-node lifetime):")
        for i, row in ranked.iterrows():
            print(f"   {i+1}. {row['Protocol']:12s}  FND={row['FND mean']:.0f}")
        print()
