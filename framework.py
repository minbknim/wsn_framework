"""WSNFramework — top-level API (19개 프로토콜, 지속성 테스트, 계층형 결과 저장).

변경 이력
---------
v7 (2026-05-13) : ALL_PROTOCOLS 11→19개로 업데이트 (논문 v7 기준 일치)
                  compare_all() docstring 수정 (19개 명시)
                  print_summary()에 LND×PDR Score 기준 순위 추가
                  AMCP-E-RL 비교 제외 사유 주석 추가
"""

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

# ── 등록 프로토콜 목록 (논문 v7 기준 19개) ───────────────────────────────────
#
# 분류        프로토콜
# ----------  -----------------------------------------------------------
# 계층형(5)   LEACH, LEACH-C, HEED, TEEN, APTEEN
# 이종계층(2) SEP, DEEC
# 체인형(1)   PEGASIS
# 멀티홉(1)   EE-LEACH
# 멀티체인(6) MCP, MCP+, AMCP-E(제안), AMCP-E-H2(제안), AMCP-E-RL(제안), DMCP(제안)
# 데이터중심(2) SPIN, RUMOR
# 위치기반(2) GEAR, GAF
#
# ※ AMCP-E-RL: 구현 완료. 단, 현 DQN v4는 고정 K=150 대비 성능 열위로
#   논문 Table 2 최종 비교에서 제외(—로 표기). compare_all()에는 포함되나
#   성능 해석 시 주의 요망. 차후 에피소딕 학습 구조로 개선 예정.

ALL_PROTOCOLS = [
    # 계층형
    "LEACH", "LEACH-C", "HEED", "TEEN", "APTEEN",
    # 이종계층
    "SEP", "DEEC",
    # 체인형
    "PEGASIS",
    # 멀티홉
    "EE-LEACH",
    # 멀티체인 (MCP 계열 + 제안 프로토콜)
    "MCP", "MCP+", "AMCP-E", "AMCP-E-H2", "AMCP-E-RL", "DMCP",
    # 데이터중심
    "SPIN", "RUMOR",
    # 위치기반
    "GEAR", "GAF",
]

# 논문 Table 2 최종 비교에 포함된 프로토콜 (AMCP-E-RL 제외)
# compare_all()은 ALL_PROTOCOLS 전체 대상, 논문 재현은 아래 목록 사용
PAPER_PROTOCOLS = [p for p in ALL_PROTOCOLS if p != "AMCP-E-RL"]


class WSNFramework:
    """
    WSN 시뮬레이션 프레임워크 최상위 API.

    주요 기능
    ----------
    run()                : 단일 프로토콜 Monte Carlo 실행
    compare()            : 여러 프로토콜 동일 환경 비교 (Monte Carlo, 고정 라운드)
    compare_until_dead() : 모든 노드가 죽을 때까지 반복 → 네트워크 지속 시간 비교
    compare_all()        : 19개 전체 프로토콜 비교 (논문 v7 기준)
    compare_paper()      : 논문 Table 2 재현용 18개 프로토콜 비교 (AMCP-E-RL 제외)
    sweep()              : 파라미터 스윕
    export_all()         : CSV / JSON / LaTeX / 그래프 일괄 저장
    save_topology()      : 초기 토폴로지 그림 저장

    결과 저장 구조
    --------------
    results/
    └── YYYYMMDD_HHMMSS/          ← 실험 시작 시각
        ├── comparison/           ← 비교 그래프 (alive_nodes.png 등)
        ├── LEACH/                ← 프로토콜별
        │   ├── initial_topology.png
        │   ├── summary.json
        │   ├── per_round.csv
        │   └── topology_snapshots/   ← 토폴로지 변화 스냅샷 (옵션)
        ├── HEED/
        └── …
    """

    def __init__(
        self,
        config: ScenarioConfig,
        output_dir: str = "results",
        use_timestamp: bool = True,
    ):
        self.config = config
        self._manager = ExperimentManager(
            config,
            output_dir=output_dir,
            use_timestamp=use_timestamp,
        )
        self.run_dir = self._manager.run_dir
        self._exporter = ResultExporter(self.run_dir)
        self._plotter = Plotter(self.run_dir)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    # ── 생성자 ────────────────────────────────────────────────────────────────

    @classmethod
    def from_yaml(
        cls,
        path: str,
        output_dir: str = "results",
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
        protocol: str,
        repetitions: Optional[int] = None,
        until_all_dead: bool = False,
        save_snapshots: bool = False,
    ) -> AggregatedResult:
        """단일 프로토콜 Monte Carlo 실행."""
        log.info(
            f"Running {protocol} ×{repetitions or self.config.simulation.repetitions}"
            f" | until_all_dead={until_all_dead}"
        )
        return self._manager.run_monte_carlo(
            protocol, repetitions,
            until_all_dead=until_all_dead,
            save_snapshots=save_snapshots,
        )

    def compare(
        self,
        protocols: List[str],
        repetitions: Optional[int] = None,
        save_snapshots: bool = False,
    ) -> Dict[str, AggregatedResult]:
        """여러 프로토콜 동일 환경 비교 (Monte Carlo, 고정 라운드 수)."""
        log.info(f"Comparing {protocols} (fixed rounds)")
        return self._manager.compare(
            protocols, repetitions,
            until_all_dead=False,
            save_snapshots=save_snapshots,
        )

    def compare_until_dead(
        self,
        protocols: List[str],
        repetitions: Optional[int] = None,
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
        repetitions: Optional[int] = None,
        until_all_dead: bool = True,
        save_snapshots: bool = False,
    ) -> Dict[str, AggregatedResult]:
        """
        19개 전체 프로토콜 비교 (논문 v7 기준).

        포함 프로토콜
        -------------
        계층형(5)   : LEACH, LEACH-C, HEED, TEEN, APTEEN
        이종계층(2) : SEP, DEEC
        체인형(1)   : PEGASIS
        멀티홉(1)   : EE-LEACH
        멀티체인(6) : MCP, MCP+, AMCP-E, AMCP-E-H2, AMCP-E-RL, DMCP
        데이터중심(2): SPIN, RUMOR
        위치기반(2) : GEAR, GAF

        참고: AMCP-E-RL은 현재 고정 K=150 대비 성능 열위 상태.
              논문 Table 2 정확한 재현은 compare_paper() 사용 권장.
        """
        log.info(f"Comparing ALL {len(ALL_PROTOCOLS)} protocols (v7)")
        return self._manager.compare(
            ALL_PROTOCOLS, repetitions,
            until_all_dead=until_all_dead,
            save_snapshots=save_snapshots,
        )

    def compare_paper(
        self,
        repetitions: Optional[int] = None,
        save_snapshots: bool = False,
    ) -> Dict[str, AggregatedResult]:
        """
        논문 Table 2 재현용 18개 프로토콜 비교.

        AMCP-E-RL은 DQN v4 성능 미성숙으로 논문에서 제외(—).
        이 메서드는 논문과 동일한 조건으로 18개 프로토콜을
        run_until_dead=True, 20회 Monte Carlo로 실행합니다.

        권장 설정 (논문 기준):
            repetitions=20, seeds 42~61, run_until_dead=True
        """
        log.info(f"Comparing PAPER {len(PAPER_PROTOCOLS)} protocols (논문 Table 2 재현)")
        return self._manager.compare(
            PAPER_PROTOCOLS,
            repetitions,
            until_all_dead=True,
            save_snapshots=save_snapshots,
        )

    def sweep(
        self,
        protocols: List[str],
        param: str,
        values: list,
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
            sub_fw = WSNFramework(cfg_copy, output_dir=str(sub_dir),
                                  use_timestamp=False)
            results[str(val)] = sub_fw._manager.compare(
                protocols, until_all_dead=until_all_dead
            )
        return results

    # ── 토폴로지 ─────────────────────────────────────────────────────────────

    def save_topology(
        self,
        output_path: Optional[str] = None,
        title: str = "Initial WSN Topology",
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
        self._plotter.plot_all(comparison)
        log.info(f"All results saved → {self.run_dir}")

    def print_summary(self, comparison: Dict[str, AggregatedResult]) -> None:
        """결과 요약 출력 (LND, PDR, Score=LND×PDR 기준 이중 순위 표시)."""
        print("\n" + "=" * 80)
        print("  WSN Protocol Comparison Summary  (논문 v7 — Score = LND × PDR)")
        print("=" * 80)
        header = (
            f"  {'Protocol':12s} {'FND':>8s} {'HND':>8s} {'LND':>9s}"
            f" {'PDR':>7s} {'Score':>10s} {'E_bal(mJ)':>10s}"
        )
        print(header)
        print("-" * 80)

        for proto, agg in comparison.items():
            score = agg.lnd_mean * agg.pdr_mean
            e_bal_mj = agg.e_bal_mean * 1000
            print(
                f"  {proto:12s} {agg.fnd_mean:8.1f} {agg.hnd_mean:8.1f}"
                f" {agg.lnd_mean:9.1f} {agg.pdr_mean:7.4f}"
                f" {score:10.0f} {e_bal_mj:10.4f}"
            )

        print("=" * 80)

        # ── LND×PDR Score 기준 순위 (논문 Table 2와 동일 기준) ──────────────
        ranked_score = sorted(
            comparison.items(),
            key=lambda x: x[1].lnd_mean * x[1].pdr_mean,
            reverse=True,
        )
        print("\n  [Score = LND × PDR 기준 순위] (논문 Table 2 기준)")
        for i, (proto, agg) in enumerate(ranked_score):
            score = agg.lnd_mean * agg.pdr_mean
            note = ""
            if agg.pdr_mean < 0.01:
                note = "  ⚠ PDR≈0 → LND 단독 지표 편향 주의"
            print(f"  {i+1:2d}. {proto:12s}  Score={score:>10.0f}"
                  f"  LND={agg.lnd_mean:>9.0f}  PDR={agg.pdr_mean:.4f}{note}")

        # ── LND 단독 순위 (참고용) ───────────────────────────────────────────
        ranked_lnd = sorted(
            comparison.items(),
            key=lambda x: x[1].lnd_mean,
            reverse=True,
        )
        print("\n  [LND 단독 순위] (참고용 — 논문에서 편향 지표로 경고)")
        for i, (proto, agg) in enumerate(ranked_lnd):
            print(f"  {i+1:2d}. {proto:12s}  LND={agg.lnd_mean:>9.0f}")

        print()

    @staticmethod
    def list_protocols() -> List[str]:
        """지원 프로토콜 목록 반환 (19개)."""
        return list_protocols()

    @staticmethod
    def all_protocols() -> List[str]:
        """ALL_PROTOCOLS 리스트 반환."""
        return list(ALL_PROTOCOLS)

    @staticmethod
    def paper_protocols() -> List[str]:
        """논문 Table 2 기준 프로토콜 리스트 반환 (AMCP-E-RL 제외)."""
        return list(PAPER_PROTOCOLS)
