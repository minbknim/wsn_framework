"""
parallel_experiment.py — 대규모 노드 병렬 실험 지원 (N=100~2000)

multiprocessing.Pool 활용으로 N=500, 1000, 2000 빠른 실험 가능
"""
from __future__ import annotations
import os, sys, time, statistics as st
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _run_single(args):
    """단일 실험 워커 (pickle 가능한 최상위 함수)."""
    pname, seed, n_nodes, max_rounds, cfg_path = args
    from wsn_framework.core.config import ScenarioConfig
    from wsn_framework.core.topology import TopologyManager
    from wsn_framework.core.energy import EnergyModel
    from wsn_framework.protocols import get_protocol

    cfg = ScenarioConfig.from_yaml(cfg_path)
    cfg.topology.num_nodes = n_nodes
    em  = EnergyModel(cfg.energy)
    topo = TopologyManager(cfg.topology, cfg.energy, seed=seed)
    topo.deploy()
    proto = get_protocol(pname)(cfg.protocol, em, cfg.comm)
    r = proto.run(topo, max_rounds, seed, 0, run_until_dead=True)
    return (seed, r.fnd, r.lnd, r.pdr, r.total_energy_consumed)


class ParallelExperiment:
    """
    대규모 노드 병렬 실험 관리자.

    Usage
    -----
    exp = ParallelExperiment(cfg_path, n_workers=4)
    results = exp.run("AMCP-E", n_nodes=500, repetitions=10)
    """

    def __init__(self, cfg_path: str,
                 n_workers: Optional[int] = None):
        self.cfg_path  = cfg_path
        self.n_workers = n_workers or min(cpu_count(), 4)

    def run(self, pname: str, n_nodes: int = 100,
            repetitions: int = 10,
            max_rounds: int = 1_000_000,
            seeds: Optional[List[int]] = None) -> Dict:
        """병렬 실험 실행."""
        if seeds is None:
            seeds = list(range(42, 42 + repetitions))

        args = [(pname, s, n_nodes, max_rounds, self.cfg_path)
                for s in seeds]

        t0 = time.time()
        if self.n_workers > 1:
            with Pool(self.n_workers) as pool:
                raw = pool.map(_run_single, args)
        else:
            raw = [_run_single(a) for a in args]

        fnds = [r[1] for r in raw]
        lnds = [r[2] for r in raw]
        pdrs = [r[3] for r in raw]

        return {
            "protocol":   pname,
            "n_nodes":    n_nodes,
            "repetitions":len(raw),
            "elapsed":    round(time.time() - t0, 2),
            "fnd_mean":   round(st.mean(fnds), 1),
            "lnd_mean":   round(st.mean(lnds), 1),
            "lnd_std":    round(st.stdev(lnds), 1) if len(lnds) > 1 else 0,
            "pdr_mean":   round(st.mean(pdrs), 4),
            "score":      round(st.mean(lnds) * st.mean(pdrs), 1),
            "raw":        raw,
        }

    def scalability_test(self, pname: str,
                         node_counts: List[int] = [100, 200, 500],
                         repetitions: int = 5) -> List[Dict]:
        """노드 수별 확장성 실험."""
        results = []
        for n in node_counts:
            r = self.run(pname, n_nodes=n, repetitions=repetitions)
            results.append(r)
            print(f"  N={n:4d}: LND={r['lnd_mean']:,.0f}  "
                  f"Score={r['score']:,.0f}  t={r['elapsed']}s")
        return results
