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
        show_links:  bool  = True,
        ch_ids:      Optional[List[int]] = None,
        cluster_map: Optional[dict]      = None,  # node_id → ch_id
        round_num:   Optional[int]       = None,
        dpi:         int   = 150,
    ) -> Path:
        """Generate and save topology figure."""
        fig, ax = plt.subplots(figsize=(8, 8))
        W, H = self.cfg.area_width, self.cfg.area_height
        ax.set_xlim(-5, W + 5)
        ax.set_ylim(-5, H + 5)
        ax.set_aspect("equal")
        ax.set_facecolor("#f8f9fa")
        ax.grid(True, alpha=0.25, linewidth=0.5)
        ax.set_xlabel("X (m)", fontsize=11)
        ax.set_ylabel("Y (m)", fontsize=11)

        # ── Draw communication links ──────────────────────────────────────────
        if show_links:
            for i, u in enumerate(self.nodes):
                if not u.alive:
                    continue
                for v in self.nodes[i + 1:]:
                    if not v.alive:
                        continue
                    if u.distance_to(v) <= tx_range:
                        ax.plot([u.x, v.x], [u.y, v.y],
                                color="#cccccc", linewidth=0.4, alpha=0.5, zorder=1)

        # ── Cluster colouring ─────────────────────────────────────────────────
        cluster_colors: dict = {}
        if cluster_map and ch_ids:
            palette = plt.cm.Set2(np.linspace(0, 1, max(len(ch_ids), 1)))
            for idx, ch in enumerate(ch_ids):
                cluster_colors[ch] = palette[idx]
            for node in self.nodes:
                if not node.alive:
                    continue
                ch = cluster_map.get(node.node_id)
                if ch is not None and ch in cluster_colors:
                    ax.scatter(node.x, node.y, s=40,
                               color=cluster_colors[ch], alpha=0.6,
                               edgecolors="none", zorder=3)

        # ── Sensor nodes ──────────────────────────────────────────────────────
        alive   = [n for n in self.nodes if n.alive]
        dead    = [n for n in self.nodes if not n.alive]
        norm    = plt.Normalize(
            vmin=0, vmax=self.energy_cfg.initial_energy
        )
        cmap    = plt.cm.RdYlGn

        if alive:
            energies = [n.energy for n in alive]
            xs_a = [n.x for n in alive]
            ys_a = [n.y for n in alive]
            sc = ax.scatter(xs_a, ys_a, c=energies, cmap=cmap, norm=norm,
                            s=50, edgecolors="#555", linewidths=0.5, zorder=4,
                            label=f"Alive ({len(alive)})")
            plt.colorbar(sc, ax=ax, label="Residual energy (J)", fraction=0.03)

        if dead:
            ax.scatter([n.x for n in dead], [n.y for n in dead],
                       marker="x", color="#cc3333", s=40, linewidths=1.2,
                       zorder=5, label=f"Dead ({len(dead)})")

        # ── Cluster heads ─────────────────────────────────────────────────────
        if ch_ids:
            ch_nodes = [n for n in self.nodes if n.node_id in ch_ids and n.alive]
            if ch_nodes:
                ax.scatter([n.x for n in ch_nodes], [n.y for n in ch_nodes],
                           marker="*", color="#1a1aff", s=220, zorder=6,
                           edgecolors="white", linewidths=0.8,
                           label=f"Cluster Head ({len(ch_nodes)})")
                # TX range circles
                for ch in ch_nodes:
                    circle = plt.Circle(
                        (ch.x, ch.y), tx_range,
                        color=cluster_colors.get(ch.node_id, "#1a1aff"),
                        fill=False, linestyle="--", linewidth=0.8, alpha=0.45
                    )
                    ax.add_patch(circle)

        # ── Base station ──────────────────────────────────────────────────────
        ax.scatter(self.bs.x, self.bs.y, marker="^", color="#000000",
                   s=260, zorder=7, label="Base Station", edgecolors="white",
                   linewidths=1.0)
        ax.annotate("BS", (self.bs.x, self.bs.y),
                    textcoords="offset points", xytext=(8, 6),
                    fontsize=9, fontweight="bold", color="#000000")

        # ── Title / legend ────────────────────────────────────────────────────
        t = title
        if round_num is not None:
            t += f"  [Round {round_num}]"
        ax.set_title(t, fontsize=13, fontweight="bold", pad=12)
        ax.legend(loc="upper right", fontsize=8, framealpha=0.85)

        # ── Stats annotation ──────────────────────────────────────────────────
        total_e = sum(n.energy for n in self.nodes)
        stats_txt = (
            f"Nodes: {len(alive)}/{len(self.nodes)} alive\n"
            f"Total residual E: {total_e:.4f} J\n"
            f"Area: {W}×{H} m²  |  Seed: {self.seed}"
        )
        ax.text(0.01, 0.01, stats_txt, transform=ax.transAxes,
                fontsize=7.5, verticalalignment="bottom",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return out

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
