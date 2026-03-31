"""Unit & integration tests for WSN Framework."""
import math, sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wsn_framework.core.config import (
    ScenarioConfig, TopologyConfig, EnergyConfig,
    CommConfig, ProtocolConfig, SimConfig,
)
from wsn_framework.core.topology import TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.protocols.builtin import get_protocol, REGISTRY
from wsn_framework.experiment.manager import ExperimentManager
from wsn_framework.experiment.metrics import MetricsCollector, Comparator
from wsn_framework.output.exporter import ResultExporter
from wsn_framework.output.plotter import Plotter


# ── helpers ───────────────────────────────────────────────────────────────────

def make_cfg(protocol="LEACH", nodes=30, rounds=150, reps=3):
    return ScenarioConfig(
        topology   = TopologyConfig(num_nodes=nodes),
        energy     = EnergyConfig(initial_energy=0.5),
        comm       = CommConfig(),
        protocol   = ProtocolConfig(name=protocol, ch_ratio=0.05),
        simulation = SimConfig(rounds=rounds, repetitions=reps, seed=42),
    )


# ── 1. Config ─────────────────────────────────────────────────────────────────

def test_config_defaults_valid():
    assert ScenarioConfig().validate()

def test_config_clone_protocol():
    cfg  = make_cfg("LEACH")
    copy = cfg.clone_for_protocol("HEED")
    assert copy.protocol.name == "HEED"
    assert cfg.protocol.name  == "LEACH"
    assert copy.run_id != cfg.run_id

def test_config_yaml_roundtrip():
    cfg = make_cfg()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.yaml")
        cfg.to_yaml(path)
        loaded = ScenarioConfig.from_yaml(path)
    assert loaded.topology.num_nodes == cfg.topology.num_nodes
    assert loaded.simulation.seed    == cfg.simulation.seed


# ── 2. Topology ───────────────────────────────────────────────────────────────

def test_topology_random_deploy():
    cfg  = make_cfg()
    topo = TopologyManager(cfg.topology, cfg.energy, seed=42).deploy()
    assert len(topo.nodes) == cfg.topology.num_nodes
    for n in topo.nodes:
        assert 0 <= n.x <= cfg.topology.area_width
        assert 0 <= n.y <= cfg.topology.area_height
        assert n.energy == cfg.energy.initial_energy

def test_topology_reproducibility():
    cfg = make_cfg()
    t1  = TopologyManager(cfg.topology, cfg.energy, seed=7).deploy()
    t2  = TopologyManager(cfg.topology, cfg.energy, seed=7).deploy()
    assert all(a.x == b.x and a.y == b.y for a, b in zip(t1.nodes, t2.nodes))

def test_topology_different_seeds():
    cfg = make_cfg()
    t1  = TopologyManager(cfg.topology, cfg.energy, seed=1).deploy()
    t2  = TopologyManager(cfg.topology, cfg.energy, seed=2).deploy()
    diffs = sum(1 for a, b in zip(t1.nodes, t2.nodes) if a.x != b.x)
    assert diffs > 0

def test_topology_figure_saved():
    cfg  = make_cfg()
    topo = TopologyManager(cfg.topology, cfg.energy, seed=42).deploy()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "topo.png")
        topo.visualize(out, tx_range=cfg.comm.tx_range)
        assert os.path.exists(out) and os.path.getsize(out) > 0


# ── 3. Energy model ───────────────────────────────────────────────────────────

def test_energy_free_space():
    em = EnergyModel(EnergyConfig())
    d  = em.threshold_distance * 0.5
    e  = em.tx_energy(4000, d)
    expected = 4000 * 50e-9 + 4000 * 100e-12 * d**2
    assert abs(e - expected) < 1e-18

def test_energy_multipath():
    em = EnergyModel(EnergyConfig())
    d  = em.threshold_distance * 2.0
    e  = em.tx_energy(4000, d)
    expected = 4000 * 50e-9 + 4000 * 0.0013e-12 * d**4
    assert abs(e - expected) < 1e-18

def test_energy_rx():
    em = EnergyModel(EnergyConfig())
    assert abs(em.rx_energy(4000) - 4000 * 50e-9) < 1e-18

def test_threshold_distance():
    em  = EnergyModel(EnergyConfig())
    d0  = math.sqrt(100e-12 / 0.0013e-12)
    assert abs(em.threshold_distance - d0) / d0 < 1e-6


# ── 4. Protocols ──────────────────────────────────────────────────────────────

import pytest

@pytest.mark.parametrize("proto", list(REGISTRY.keys()))
def test_protocol_runs(proto):
    cfg  = make_cfg(proto, nodes=30, rounds=100, reps=1)
    em   = EnergyModel(cfg.energy)
    topo = TopologyManager(cfg.topology, cfg.energy, seed=42).deploy()
    p    = get_protocol(proto)(cfg.protocol, em, cfg.comm)
    r    = p.run(topo, 100, 42, 0)
    assert r.protocol == proto
    assert r.fnd >= 0
    assert r.lnd >= r.fnd
    assert 0.0 <= r.pdr <= 1.0
    assert r.residual_energy_final >= 0

@pytest.mark.parametrize("proto", ["LEACH", "HEED", "SEP"])
def test_energy_monotone(proto):
    cfg  = make_cfg(proto, nodes=30, rounds=200, reps=1)
    em   = EnergyModel(cfg.energy)
    topo = TopologyManager(cfg.topology, cfg.energy, seed=42).deploy()
    p    = get_protocol(proto)(cfg.protocol, em, cfg.comm)
    r    = p.run(topo, 200, 42, 0)
    energies = [s.total_energy for s in r.round_stats]
    violations = sum(1 for i in range(len(energies)-1) if energies[i] < energies[i+1])
    assert violations == 0, f"{proto}: energy increased in {violations} rounds"

def test_same_seed_same_result():
    """동일 seed → 동일 FND 보장 (재현성 핵심 테스트)"""
    cfg = make_cfg("LEACH", nodes=30, rounds=100)
    em  = EnergyModel(cfg.energy)
    def run_once():
        topo = TopologyManager(cfg.topology, cfg.energy, seed=42).deploy()
        p = get_protocol("LEACH")(cfg.protocol, em, cfg.comm)
        return p.run(topo, 100, 42, 0).fnd
    assert run_once() == run_once()


# ── 5. ExperimentManager ──────────────────────────────────────────────────────

def test_manager_single_run():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = make_cfg("LEACH", nodes=25, rounds=80, reps=1)
        mgr = ExperimentManager(cfg, output_dir=tmp)
        r   = mgr.run_single("LEACH", seed=42, rep_id=0, save_topology_fig=False)
        assert r.protocol == "LEACH"
        assert r.fnd >= 0

def test_manager_monte_carlo():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = make_cfg("HEED", nodes=25, rounds=80, reps=5)
        mgr = ExperimentManager(cfg, output_dir=tmp)
        agg = mgr.run_monte_carlo("HEED", repetitions=5, save_topology_fig=False)
        assert agg.repetitions == 5
        assert agg.fnd_mean > 0
        assert agg.fnd_std  >= 0

def test_manager_compare_protocols():
    with tempfile.TemporaryDirectory() as tmp:
        cfg  = make_cfg("LEACH", nodes=25, rounds=80, reps=3)
        mgr  = ExperimentManager(cfg, output_dir=tmp)
        comp = mgr.compare(["LEACH","HEED","SEP"], repetitions=3, save_topology_fig=False)
        assert set(comp.keys()) == {"LEACH", "HEED", "SEP"}
        # 모든 프로토콜이 동일 시드로 실행됐는지: 각각 3개 raw result
        for agg in comp.values():
            assert agg.repetitions == 3

def test_topology_figures_created():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = make_cfg("LEACH", nodes=25, rounds=80, reps=2)
        mgr = ExperimentManager(cfg, output_dir=tmp)
        mgr.run_monte_carlo("LEACH", repetitions=2, save_topology_fig=True)
        pngs = [f for _, _, files in os.walk(tmp) for f in files if f.endswith(".png")]
        assert len(pngs) >= 1


# ── 6. Comparator ─────────────────────────────────────────────────────────────

def _get_comp(tmp):
    cfg  = make_cfg("LEACH", nodes=25, rounds=80, reps=3)
    mgr  = ExperimentManager(cfg, output_dir=tmp)
    return mgr.compare(["LEACH","HEED","SEP"], repetitions=3, save_topology_fig=False)

def test_comparator_summary_df():
    with tempfile.TemporaryDirectory() as tmp:
        comp = _get_comp(tmp)
        df   = Comparator(comp).summary_dataframe()
        assert set(["LEACH","HEED","SEP"]).issubset(set(df.index))
        assert "FND mean" in df.columns

def test_comparator_ttest_diagonal():
    with tempfile.TemporaryDirectory() as tmp:
        comp = _get_comp(tmp)
        pval = Comparator(comp).pairwise_ttest("fnd")
        for p in comp:
            assert pval.loc[p, p] == 1.0

def test_comparator_rank():
    with tempfile.TemporaryDirectory() as tmp:
        comp   = _get_comp(tmp)
        ranked = Comparator(comp).rank("fnd_mean", ascending=False)
        assert len(ranked) == 3


# ── 7. Exporter + Plotter ─────────────────────────────────────────────────────

def test_exporter_all_files():
    with tempfile.TemporaryDirectory() as tmp:
        comp = _get_comp(tmp)
        exp  = ResultExporter(tmp)
        paths = [
            exp.export_summary_csv(comp),
            exp.export_summary_json(comp),
            exp.export_latex_table(comp),
            exp.export_per_round_csv(comp, "alive"),
            exp.export_per_round_csv(comp, "energy"),
            exp.export_ttest(comp, "fnd"),
        ]
        for p in paths:
            assert os.path.exists(p) and os.path.getsize(p) > 0

def test_plotter_all_figures():
    with tempfile.TemporaryDirectory() as tmp:
        comp = _get_comp(tmp)
        plt  = Plotter(tmp)
        figs = [
            plt.plot_alive_nodes(comp),
            plt.plot_energy(comp),
            plt.plot_lifetime_bars(comp),
            plt.plot_pdr(comp),
            plt.plot_energy_balance(comp),
            plt.plot_ttest_heatmap(comp),
            plt.plot_dashboard(comp),
        ]
        for f in figs:
            assert os.path.exists(f) and os.path.getsize(f) > 0


# ── 8. WSNFramework top-level API ─────────────────────────────────────────────

def test_framework_from_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        cfg  = make_cfg()
        path = os.path.join(tmp, "s.yaml")
        cfg.to_yaml(path)
        from wsn_framework.framework import WSNFramework
        fw = WSNFramework.from_yaml(path, output_dir=tmp)
        assert fw.config.topology.num_nodes == cfg.topology.num_nodes

def test_framework_run():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = make_cfg("LEACH", nodes=25, rounds=80, reps=3)
        from wsn_framework.framework import WSNFramework
        fw  = WSNFramework(cfg, output_dir=tmp)
        agg = fw.run("LEACH", repetitions=3)
        assert agg.fnd_mean >= 0

def test_framework_compare_and_export():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = make_cfg("LEACH", nodes=25, rounds=80, reps=3)
        from wsn_framework.framework import WSNFramework
        fw   = WSNFramework(cfg, output_dir=tmp)
        comp = fw.compare(["LEACH","SEP"], repetitions=3)
        fw.export_all(comp)
        # CSV + JSON + figures 존재 확인
        assert os.path.exists(os.path.join(tmp, "summary.csv"))
        assert os.path.exists(os.path.join(tmp, "summary.json"))
        pngs = [f for _, _, fs in os.walk(tmp) for f in fs if f.endswith(".png")]
        assert len(pngs) >= 7   # dashboard + 6 charts + topology

def test_framework_save_topology():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = make_cfg()
        from wsn_framework.framework import WSNFramework
        fw  = WSNFramework(cfg, output_dir=tmp)
        out = os.path.join(tmp, "topo.png")
        fw.save_topology(output_path=out)
        assert os.path.exists(out) and os.path.getsize(out) > 0
