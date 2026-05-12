"""ExperimentManager — 병렬 Monte Carlo 지원, 폴더 구조 자동화."""
from __future__ import annotations
import copy, csv, logging, os, sys, tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import yaml

log = logging.getLogger(__name__)


def _bar(label: str, done: int, total: int) -> None:
    pct = int(done / total * 40)
    bar = "█" * pct + "░" * (40 - pct)
    sys.stdout.write(f"\r  {label:12s} [{bar}] {done}/{total}")
    sys.stdout.flush()
    if done == total:
        sys.stdout.write("\n")


def _safe_name(name: str) -> str:
    return name.replace("+", "plus").replace("-", "_")


def _proto_dir(run_dir: Path, proto: str) -> Path:
    d = run_dir / _safe_name(proto)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── 프로세스 풀 워커 ─────────────────────────────────────────────────────────
def _worker(args: tuple):
    (cfg_yaml, proto_name, seed, rep_id,
     run_until_dead, topo_frames_path, topo_save_interval,
     save_initial, initial_topo_path) = args

    # 자식 프로세스 경로 설정
    root = str(Path(__file__).resolve().parent.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)

    from wsn_framework.core.config import ScenarioConfig
    from wsn_framework.core.topology import TopologyManager
    from wsn_framework.core.energy import EnergyModel
    from wsn_framework.protocols import get_protocol

    cfg = ScenarioConfig.from_yaml(cfg_yaml)
    cfg.simulation.seed = seed

    topo = TopologyManager(cfg.topology, cfg.energy, seed=seed)
    topo.deploy()

    if save_initial and initial_topo_path:
        try:
            topo.visualize(Path(initial_topo_path),
                           title=f"Initial Topology — {proto_name}")
        except Exception:
            pass

    topo_dir = Path(topo_frames_path) if topo_frames_path else None
    em    = EnergyModel(cfg.energy)
    proto = get_protocol(proto_name)(cfg.protocol, em, cfg.comm)
    return proto.run(
        topo, cfg.simulation.rounds, seed, rep_id,
        run_until_dead=run_until_dead,
        topo_save_dir=topo_dir,
        topo_save_interval=topo_save_interval,
    )


class ExperimentManager:
    def __init__(
        self,
        base_config,
        output_dir: str = "results",
        run_timestamp: Optional[str] = None,
        max_workers: Optional[int] = None,
    ):
        from wsn_framework.core.config import ScenarioConfig
        self.base_cfg    = base_config
        self.base_output = Path(output_dir)
        self.base_output.mkdir(parents=True, exist_ok=True)
        self.run_ts      = run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir     = self.base_output / self.run_ts
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers or max(1, (os.cpu_count() or 4) - 1)
        print(f"  [결과 폴더] {self.run_dir}")
        print(f"  [병렬 워커] {self.max_workers}개")

        # cfg를 임시 YAML로 저장 (자식 프로세스에서 로드)
        self._cfg_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        base_config.to_yaml(self._cfg_tmp.name)
        self._cfg_tmp.close()
        self._cfg_yaml = self._cfg_tmp.name

    def __del__(self):
        try:
            if hasattr(self, "_cfg_yaml") and Path(self._cfg_yaml).exists():
                os.unlink(self._cfg_yaml)
        except Exception:
            pass

    # ── 단일 실행 (직접) ──────────────────────────────────────────────────────
    def run_single(
        self,
        protocol_name: str,
        seed: int,
        rep_id: int = 0,
        run_until_dead: bool = False,
        save_topo_changes: bool = False,
        topo_save_interval: int = 100,
        save_initial_topo: bool = True,
    ):
        from wsn_framework.core.config import ScenarioConfig
        from wsn_framework.core.topology import TopologyManager
        from wsn_framework.core.energy import EnergyModel
        from wsn_framework.protocols import get_protocol

        cfg = self.base_cfg.clone_for_protocol(protocol_name)
        cfg.simulation.seed = seed
        topo = TopologyManager(cfg.topology, cfg.energy, seed=seed)
        topo.deploy()
        proto_out = _proto_dir(self.run_dir, protocol_name)

        if save_initial_topo and rep_id == 0:
            topo.visualize(
                proto_out / f"topology_initial_seed{seed}.png",
                title=f"Initial Topology — {protocol_name}"
            )

        topo_dir = (proto_out / "topology_frames") if (save_topo_changes and rep_id == 0) else None
        em    = EnergyModel(cfg.energy)
        proto = get_protocol(protocol_name)(cfg.protocol, em, cfg.comm)
        return proto.run(
            topo, cfg.simulation.rounds, seed, rep_id,
            run_until_dead=run_until_dead,
            topo_save_dir=topo_dir,
            topo_save_interval=topo_save_interval,
        )

    # ── Monte Carlo (병렬) ────────────────────────────────────────────────────
    def run_monte_carlo(
        self,
        protocol_name: str,
        repetitions: Optional[int] = None,
        run_until_dead: bool = False,
        save_topo_changes: bool = False,
        topo_save_interval: int = 100,
    ):
        reps      = repetitions or self.base_cfg.simulation.repetitions
        base_seed = self.base_cfg.simulation.seed
        proto_out = _proto_dir(self.run_dir, protocol_name)
        frames_path = str(proto_out / "topology_frames") if save_topo_changes else None
        init_path   = str(proto_out / f"topology_initial_seed{base_seed}.png")

        args_list = [
            (
                self._cfg_yaml, protocol_name, base_seed + rep, rep,
                run_until_dead,
                frames_path if rep == 0 else None,
                topo_save_interval,
                rep == 0,
                init_path if rep == 0 else None,
            )
            for rep in range(reps)
        ]

        results = [None] * reps
        done = 0
        n_workers = min(self.max_workers, reps)

        if n_workers > 1:
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                futures = {ex.submit(_worker, a): i
                           for i, a in enumerate(args_list)}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        results[idx] = fut.result()
                    except Exception as e:
                        log.error(f"[{protocol_name}] rep {idx} 실패: {e}")
                        raise
                    done += 1
                    _bar(protocol_name, done, reps)
        else:
            for i, a in enumerate(args_list):
                results[i] = _worker(a)
                done += 1
                _bar(protocol_name, done, reps)

        agg = self._aggregate(protocol_name, results)
        self._save_proto_summary(protocol_name, agg)
        return agg

    # ── 다중 프로토콜 비교 ────────────────────────────────────────────────────
    def compare(
        self,
        protocols: List[str],
        repetitions: Optional[int] = None,
        run_until_dead: bool = False,
        save_topo_changes: bool = False,
        topo_save_interval: int = 100,
    ) -> Dict[str, any]:
        comparison = {}
        for proto in protocols:
            agg = self.run_monte_carlo(
                proto, repetitions,
                run_until_dead=run_until_dead,
                save_topo_changes=save_topo_changes,
                topo_save_interval=topo_save_interval,
            )
            comparison[proto] = agg
        self._save_comparison_summary(comparison)
        return comparison

    # ── 집계 ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _aggregate(proto: str, results: list):
        from wsn_framework.core.result import AggregatedResult
        if not results:
            return AggregatedResult(protocol=proto, repetitions=0)
        def _s(vals):
            a = np.array(vals, float)
            return float(np.mean(a)), float(np.std(a))
        agg = AggregatedResult(protocol=proto, repetitions=len(results))
        agg.fnd_mean, agg.fnd_std     = _s([r.fnd for r in results])
        agg.hnd_mean, agg.hnd_std     = _s([r.hnd for r in results])
        agg.lnd_mean, agg.lnd_std     = _s([r.lnd for r in results])
        agg.pdr_mean, agg.pdr_std     = _s([r.pdr for r in results])
        agg.e_bal_mean, agg.e_bal_std = _s([r.energy_balance_var for r in results])
        agg.e_consumed_mean, _        = _s([r.total_energy_consumed for r in results])
        agg.avg_ch_mean, _            = _s([r.avg_ch_count for r in results])
        agg.raw = results
        return agg

    # ── 요약 저장 ─────────────────────────────────────────────────────────────
    def _save_proto_summary(self, proto: str, agg) -> None:
        fp = _proto_dir(self.run_dir, proto) / "summary.txt"
        lines = [
            f"Protocol   : {proto}",
            f"Repetitions: {agg.repetitions}",
            f"FND        : {agg.fnd_mean:.1f} ± {agg.fnd_std:.1f}",
            f"HND        : {agg.hnd_mean:.1f} ± {agg.hnd_std:.1f}",
            f"LND        : {agg.lnd_mean:.1f} ± {agg.lnd_std:.1f}",
            f"PDR        : {agg.pdr_mean:.4f} ± {agg.pdr_std:.4f}",
            f"E-Consumed : {agg.e_consumed_mean:.4f} J",
            f"E-Balance  : {agg.e_bal_mean:.6f}",
            f"Avg CH/rnd : {agg.avg_ch_mean:.2f}",
        ]
        fp.write_text("\n".join(lines) + "\n")

    def _save_comparison_summary(self, comparison: dict) -> None:
        fp = self.run_dir / "comparison_summary.csv"
        fields = ["Protocol", "FND_mean", "FND_std",
                  "HND_mean", "HND_std", "LND_mean", "LND_std",
                  "PDR_mean", "E_consumed_J", "E_balance"]
        with open(fp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for proto, agg in comparison.items():
                w.writerow({
                    "Protocol":     proto,
                    "FND_mean":     f"{agg.fnd_mean:.1f}",
                    "FND_std":      f"{agg.fnd_std:.1f}",
                    "HND_mean":     f"{agg.hnd_mean:.1f}",
                    "HND_std":      f"{agg.hnd_std:.1f}",
                    "LND_mean":     f"{agg.lnd_mean:.1f}",
                    "LND_std":      f"{agg.lnd_std:.1f}",
                    "PDR_mean":     f"{agg.pdr_mean:.4f}",
                    "E_consumed_J": f"{agg.e_consumed_mean:.4f}",
                    "E_balance":    f"{agg.e_bal_mean:.6f}",
                })
        print(f"  [비교 요약] {fp}")

    # ── 파라미터 스윕 ─────────────────────────────────────────────────────────
    def sweep(self, protocols, param, values, repetitions=None, run_until_dead=False):
        results = {}
        for val in values:
            cfg_copy = copy.deepcopy(self.base_cfg)
            parts = param.split(".")
            obj = cfg_copy
            for p in parts[:-1]:
                obj = getattr(obj, p)
            setattr(obj, parts[-1], val)
            ts  = f"{self.run_ts}_{param.split('.')[-1]}_{val}"
            sub = ExperimentManager(cfg_copy, str(self.base_output), ts, self.max_workers)
            results[str(val)] = sub.compare(protocols, repetitions, run_until_dead=run_until_dead)
        return results
