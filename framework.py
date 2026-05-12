"""WSNFramework — top-level API (11개 프로토콜, 지속성 테스트, 계층형 결과 저장)."""
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
from wsn_framework.protocols import list_protocols

log = logging.getLogger(__name__)

# 기본 11개 프로토콜
ALL_PROTOCOLS = [
    "LEACH", "LEACH-C", "HEED", "PEGASIS",
    "TEEN", "APTEEN", "SEP", "DEEC",
    "EE-LEACH", "MCP", "MCP+",
]


class WSNFramework:
    """
    WSN 시뮬레이션 프레임워크 최상위 API.

    주요 기능
    ----------
    compare()           : 여러 프로토콜 동일 환경 비교 (Monte Carlo)
    compare_until_dead(): 모든 노드가 죽을 때까지 반복 → 네트워크 지속 시간 비교
    export_all()        : CSV / JSON / LaTeX / 그래프 일괄 저장
    save_topology()     : 초기 토폴로지 그림 저장

    결과 저장 구조
    --------------
    results/
      YYYYMMDD_HHMMSS/           ← 실험 시작 시각
        comparison/              ← 비교 그래프 (alive_nodes.png 등)
        LEACH/                   ← 프로토콜별
          initial_topology.png
          summary.json
          per_round.csv
          topology_snapshots/    ← 토폴로지 변화 스냅샷 (옵션)
        HEED/
          …
    """

    def __init__(
        self,
        config:        ScenarioConfig,
        output_dir:    str  = "results",
        use_timestamp: bool = True,
    ):
        self.config = config
        self._manager = ExperimentManager(
            config,
            output_dir=output_dir,
            use_timestamp=use_timestamp,
        )
        self.run_dir   = self._manager.run_dir
        self._exporter = ResultExporter(self.run_dir)
        self._plotter  = Plotter(self.run_dir)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    # ── 생성자 ────────────────────────────────────────────────────────────────

    @classmethod
    def from_yaml(
        cls,
        path:          str,
        output_dir:    str  = "results",
        use_timestamp: bool = True,
    ) -> "WSNFramework":
        cfg = ScenarioConfig.from_yaml(path)
        cfg.validate()
        return cls(cfg, output_dir=output_dir, use_timestamp=use_timestamp)

    @classmethod
    def from_defaults(cls, output_dir: str = "results") -> "WSNFramework":
        default = Path(__file__).parent / "configs" / "default_scenario.yaml"
        return cls.from_yaml(str(default), output_dir=output_dir)

    # ── 실행 API ──────────────────────────────────────────────────────────────

    def run(
        self,
        protocol:       str,
        repetitions:    Optional[int] = None,
        until_all_dead: bool = False,
        save_snapshots: bool = False,
    ) -> AggregatedResult:
        """단일 프로토콜 Monte Carlo 실행."""
        log.info(f"Running {protocol} ×{repetitions or self.config.simulation.repetitions}"
                 f" | until_all_dead={until_all_dead}")
        return self._manager.run_monte_carlo(
            protocol, repetitions,
            until_all_dead=until_all_dead,
            save_snapshots=save_snapshots,
        )

    def compare(
        self,
        protocols:      List[str],
        repetitions:    Optional[int] = None,
        save_snapshots: bool = False,
    ) -> Dict[str, AggregatedResult]:
        """
        여러 프로토콜 동일 환경 비교 (Monte Carlo, 고정 라운드 수).
        """
        log.info(f"Comparing {protocols} (fixed rounds)")
        return self._manager.compare(
            protocols, repetitions,
            until_all_dead=False,
            save_snapshots=save_snapshots,
        )

    def compare_until_dead(
        self,
        protocols:      List[str],
        repetitions:    Optional[int] = None,
        save_snapshots: bool = False,
    ) -> Dict[str, AggregatedResult]:
        """
        모든 노드가 죽을 때까지 반복 → 네트워크 지속 시간(LND) 비교.
        고정 라운드 제한 없음.
        """
        log.info(f"Comparing {protocols} (until ALL nodes dead)")
        return self._manager.compare(
            protocols, repetitions,
            until_all_dead=True,
            save_snapshots=save_snapshots,
        )

    def compare_all(
        self,
        repetitions:    Optional[int] = None,
        until_all_dead: bool = True,
        save_snapshots: bool = False,
    ) -> Dict[str, AggregatedResult]:
        """11개 전체 프로토콜 비교."""
        return self._manager.compare(
            ALL_PROTOCOLS, repetitions,
            until_all_dead=until_all_dead,
            save_snapshots=save_snapshots,
        )

    def sweep(
        self,
        protocols:      List[str],
        param:          str,
        values:         list,
        until_all_dead: bool = False,
    ) -> Dict[str, Dict[str, AggregatedResult]]:
        """파라미터 스윕."""
        import copy
        results: Dict[str, Dict[str, AggregatedResult]] = {}
        for val in values:
            log.info(f"Sweep {param}={val}")
            cfg_copy = copy.deepcopy(self.config)
            parts = param.split(".")
            obj = cfg_copy
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], val)
            cfg_copy.validate()

            sub_dir = self.run_dir / f"sweep_{param}_{val}"
            sub_fw  = WSNFramework(cfg_copy, output_dir=str(sub_dir),
                                   use_timestamp=False)
            results[str(val)] = sub_fw._manager.compare(
                protocols, until_all_dead=until_all_dead
            )
        return results

    # ── 토폴로지 ─────────────────────────────────────────────────────────────

    def save_topology(
        self,
        output_path: Optional[str] = None,
        title:       str = "Initial WSN Topology",
    ) -> Path:
        topo = TopologyManager(
            self.config.topology,
            self.config.energy,
            seed=self.config.simulation.seed,
        )
        topo.deploy()
        path = output_path or str(self.run_dir / "initial_topology.png")
        return topo.visualize(path, title=title,
                              tx_range=self.config.comm.tx_range)

    # ── 내보내기 ─────────────────────────────────────────────────────────────

    def export_all(self, comparison: Dict[str, AggregatedResult]) -> None:
        """CSV / JSON / LaTeX / 그래프 일괄 저장."""
        log.info("Exporting results …")
        saved = self._exporter.export_all(comparison)
        for k, p in saved.items():
            log.info(f"  {k}: {p}")
        # 비교 그래프
        self._plotter.plot_all(comparison)
        log.info(f"All results saved → {self.run_dir}")

    def print_summary(self, comparison: Dict[str, AggregatedResult]) -> None:
        try:
            from tabulate import tabulate
            use_tabulate = True
        except ImportError:
            use_tabulate = False

        print("\n" + "="*72)
        print("  WSN Protocol Comparison Summary")
        print("="*72)
        header = f"{'Protocol':12s} {'FND':>8s} {'HND':>8s} {'LND':>8s} {'PDR':>7s} {'E_bal':>8s}"
        print(header)
        print("-"*60)
        for proto, agg in comparison.items():
            print(f"  {proto:12s} {agg.fnd_mean:8.1f} {agg.hnd_mean:8.1f}"
                  f" {agg.lnd_mean:8.1f} {agg.pdr_mean:7.4f} {agg.e_bal_mean*1000:8.4f}")
        print("="*72)
        # FND 기준 순위
        ranked = sorted(comparison.items(), key=lambda x: x[1].lnd_mean, reverse=True)
        print("\n  Ranking by LND (longer = better network duration):")
        for i, (proto, agg) in enumerate(ranked):
            print(f"   {i+1:2d}. {proto:12s}  LND={agg.lnd_mean:.0f}  "
                  f"FND={agg.fnd_mean:.0f}  HND={agg.hnd_mean:.0f}")
        print()

    @staticmethod
    def list_protocols() -> List[str]:
        """지원 프로토콜 목록 반환."""
        return list_protocols()
