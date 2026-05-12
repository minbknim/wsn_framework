"""TopologyManager — node deployment + topology visualisation."""
from __future__ import annotations
import math, random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import networkx as nx

from .config import TopologyConfig, EnergyConfig


# ── Node model ────────────────────────────────────────────────────────────────

@dataclass
class SensorNode:
    node_id:        int
    x:              float
    y:              float
    initial_energy: float
    energy:         float = 0.0
    is_ch:          bool  = False
    cluster_head_id: Optional[int] = None
    alive:          bool  = True

    def __post_init__(self):
        self.energy = self.initial_energy

    def distance_to(self, other: "SensorNode") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def distance_to_point(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)


@dataclass
class BaseStation:
    x: float
    y: float
    node_id: int = -1


# ── Manager ───────────────────────────────────────────────────────────────────

class TopologyManager:
    def __init__(
        self,
        topo_cfg:   TopologyConfig,
        energy_cfg: EnergyConfig,
        seed:       int = 42,
    ):
        self.cfg        = topo_cfg
        self.energy_cfg = energy_cfg
        self.seed       = seed
        self.nodes:  List[SensorNode] = []
        self.bs:     BaseStation      = BaseStation(*topo_cfg.bs_position)
        self._rng    = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)

    # ── Deployment ────────────────────────────────────────────────────────────

    def deploy(self) -> "TopologyManager":
        """Deploy nodes according to strategy."""
        strategy = self.cfg.deployment
        n = self.cfg.num_nodes
        W, H = self.cfg.area_width, self.cfg.area_height

        if strategy == "random":
            xs = self._np_rng.uniform(0, W, n)
            ys = self._np_rng.uniform(0, H, n)
        elif strategy == "grid":
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            gx = np.linspace(W / (2 * cols), W - W / (2 * cols), cols)
            gy = np.linspace(H / (2 * rows), H - H / (2 * rows), rows)
            xx, yy = np.meshgrid(gx, gy)
            xs, ys = xx.ravel()[:n], yy.ravel()[:n]
        elif strategy == "uniform":
            # Poisson-disk-like uniform coverage
            xs = self._np_rng.uniform(0, W, n)
            ys = self._np_rng.uniform(0, H, n)
        else:
            raise ValueError(f"Unknown deployment strategy: {strategy}")

        # Assign energy per heterogeneity tier
        energies = self._assign_energies(n)
        self.nodes = [
            SensorNode(i, float(xs[i]), float(ys[i]), energies[i])
            for i in range(n)
        ]
        return self

    def _assign_energies(self, n: int) -> List[float]:
        if not self.energy_cfg.heterogeneous:
            return [self.energy_cfg.initial_energy] * n
        levels   = self.energy_cfg.het_levels
        ratios   = self.energy_cfg.het_ratios
        fracs    = self.energy_cfg.het_fractions
        base_e   = self.energy_cfg.initial_energy
        energies = []
        for i in range(n):
            rnd = self._rng.random()
            cum = 0.0
            for lvl in range(levels):
                cum += fracs[lvl]
                if rnd <= cum:
                    energies.append(base_e * ratios[lvl])
                    break
            else:
                energies.append(base_e * ratios[-1])
        return energies

    # ── Graph helpers ─────────────────────────────────────────────────────────

    def build_graph(self, tx_range: float) -> nx.Graph:
        G = nx.Graph()
        for node in self.nodes:
            G.add_node(node.node_id, pos=(node.x, node.y),
                       energy=node.energy, alive=node.alive)
        for i, u in enumerate(self.nodes):
            for v in self.nodes[i+1:]:
                if u.distance_to(v) <= tx_range and u.alive and v.alive:
                    G.add_edge(u.node_id, v.node_id,
                               weight=round(u.distance_to(v), 2))
        return G

    # ── Visualisation ─────────────────────────────────────────────────────────

    def visualize(
        self,
        output_path: str | Path,
        title:       str   = "WSN Topology",
        tx_range:    float = 100.0,
        show_links:  bool  = True,   # 라운드 프레임에서는 False 권장
        ch_ids:      Optional[List[int]] = None,
        cluster_map: Optional[dict]      = None,
        round_num:   Optional[int]       = None,
        dpi:         int   = 100,
    ) -> Path:
        """Generate and save topology figure (최적화 버전)."""
        fig, ax = plt.subplots(figsize=(7, 7))
        W, H = self.cfg.area_width, self.cfg.area_height
        ax.set_xlim(-5, W + 5)
        ax.set_ylim(-5, H + 5)
        ax.set_aspect("equal")
        ax.set_facecolor("#f8f9fa")
        ax.grid(True, alpha=0.25, linewidth=0.5)
        ax.set_xlabel("X (m)", fontsize=10)
        ax.set_ylabel("Y (m)", fontsize=10)

        alive_nodes = [n for n in self.nodes if n.alive]
        dead_nodes  = [n for n in self.nodes if not n.alive]
        ch_set      = set(ch_ids) if ch_ids else set()

        # ── 클러스터 멤버-CH 연결선 (라운드 프레임용) ─────────────────────────
        if cluster_map and ch_set and not show_links:
            node_map = {n.node_id: n for n in alive_nodes}
            for nid, cid in cluster_map.items():
                if nid != cid and nid in node_map and cid in node_map:
                    n_ = node_map[nid]
                    c_ = node_map[cid]
                    ax.plot([n_.x, c_.x], [n_.y, c_.y],
                            color="#aaaaaa", linewidth=0.5, alpha=0.4, zorder=1)

        # ── 전통적인 링크 (초기 토폴로지용) ──────────────────────────────────
        elif show_links and len(alive_nodes) <= 60:
            # N<=60일 때만 O(N²) 링크 그리기
            for i, u in enumerate(alive_nodes):
                for v in alive_nodes[i+1:]:
                    if u.distance_to(v) <= tx_range:
                        ax.plot([u.x, v.x], [u.y, v.y],
                                color="#cccccc", linewidth=0.3, alpha=0.4, zorder=1)

        # ── 클러스터 색상 배경 (ch_ids 있을 때만) ────────────────────────────
        cluster_colors: dict = {}
        if ch_set and cluster_map:
            palette = plt.cm.Set2(np.linspace(0, 1, max(len(ch_set), 1)))
            for idx, ch in enumerate(sorted(ch_set)):
                cluster_colors[ch] = palette[idx % len(palette)]
            # 멤버 노드 배경색
            mem_xs, mem_ys, mem_cols = [], [], []
            for node in alive_nodes:
                if node.node_id in ch_set:
                    continue
                ch = cluster_map.get(node.node_id)
                if ch in cluster_colors:
                    mem_xs.append(node.x); mem_ys.append(node.y)
                    mem_cols.append(cluster_colors[ch])
            if mem_xs:
                ax.scatter(mem_xs, mem_ys, s=50, c=mem_cols, alpha=0.35,
                           edgecolors="none", zorder=2)

        # ── 생존 노드 (에너지 컬러맵) ─────────────────────────────────────────
        if alive_nodes:
            energies = [n.energy for n in alive_nodes]
            norm = plt.Normalize(vmin=0, vmax=self.energy_cfg.initial_energy)
            sc = ax.scatter([n.x for n in alive_nodes],
                            [n.y for n in alive_nodes],
                            c=energies, cmap="RdYlGn", norm=norm,
                            s=45, edgecolors="#444", linewidths=0.4, zorder=4,
                            label=f"Alive ({len(alive_nodes)})")
            plt.colorbar(sc, ax=ax, label="Residual E (J)", fraction=0.03, pad=0.02)

        # ── 사망 노드 ─────────────────────────────────────────────────────────
        if dead_nodes:
            ax.scatter([n.x for n in dead_nodes], [n.y for n in dead_nodes],
                       marker="x", color="#cc3333", s=35, linewidths=1.0,
                       zorder=3, label=f"Dead ({len(dead_nodes)})")

        # ── CH 표시 (★) ──────────────────────────────────────────────────────
        if ch_set:
            ch_alive = [n for n in alive_nodes if n.node_id in ch_set]
            if ch_alive:
                for ch in ch_alive:
                    col = cluster_colors.get(ch.node_id, "#1a1aff")
                    ax.scatter(ch.x, ch.y, marker="*", color=col, s=200,
                               edgecolors="white", linewidths=0.6, zorder=6)
                # 대표 레전드 항목 하나만
                ax.scatter([], [], marker="*", color="#1a1aff", s=200,
                           label=f"CH ({len(ch_alive)})")

        # ── BS ────────────────────────────────────────────────────────────────
        ax.scatter(self.bs.x, self.bs.y, marker="^", color="#000000",
                   s=220, zorder=7, label="BS", edgecolors="white", linewidths=0.8)
        ax.annotate("BS", (self.bs.x, self.bs.y),
                    textcoords="offset points", xytext=(6, 5), fontsize=8,
                    fontweight="bold", color="#000000")

        # ── 제목 / 범례 ───────────────────────────────────────────────────────
        t_str = title if round_num is None else f"{title}  [Round {round_num}]"
        ax.set_title(t_str, fontsize=11, fontweight="bold", pad=8)
        ax.legend(loc="upper right", fontsize=7, framealpha=0.85,
                  markerscale=0.8)

        # ── 통계 텍스트 ───────────────────────────────────────────────────────
        total_e = sum(n.energy for n in self.nodes)
        ax.text(0.01, 0.01,
                f"Alive: {len(alive_nodes)}/{len(self.nodes)}\n"
                f"ResidualE: {total_e:.3f}J",
                transform=ax.transAxes, fontsize=7.5,
                verticalalignment="bottom",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return out

    # ── NS3 helpers ───────────────────────────────────────────────────────────
    # ── NS3 helpers ───────────────────────────────────────────────────────────

    def to_ns3_positions_cpp(self) -> str:
        """Return C++ snippet that places nodes in NS-3."""
        lines = []
        for n in self.nodes:
            lines.append(
                f"  mobility.Install(nodes.Get({n.node_id}));\n"
                f"  Ptr<MobilityModel> mob{n.node_id} = "
                f"nodes.Get({n.node_id})->GetObject<MobilityModel>();\n"
                f"  mob{n.node_id}->SetPosition(Vector({n.x:.2f}, {n.y:.2f}, 0.0));"
            )
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.nodes)
