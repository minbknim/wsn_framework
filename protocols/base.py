"""Abstract base class for all WSN routing protocols."""
from __future__ import annotations
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional

from wsn_framework.core.topology import SensorNode, BaseStation, TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.core.config import ProtocolConfig, CommConfig
from wsn_framework.core.result import ExperimentResult, RoundStats


class BaseProtocol(ABC):
    name:          str  = "BASE"
    default_params: dict = {}

    def __init__(
        self,
        proto_cfg:  ProtocolConfig,
        energy_model: EnergyModel,
        comm_cfg:   CommConfig,
    ):
        self.cfg   = proto_cfg
        self.em    = energy_model
        self.comm  = comm_cfg
        self.params = {**self.default_params, **proto_cfg.params}

    # ── Public interface ──────────────────────────────────────────────────────

    def run(
        self,
        topology: TopologyManager,
        rounds:   int,
        seed:     int,
        rep_id:   int,
    ) -> ExperimentResult:
        nodes = topology.nodes
        bs    = topology.bs
        result = ExperimentResult(
            protocol=self.name, seed=seed, repetition_id=rep_id
        )
        total_packets = 0
        ch_counts     = []
        fnd_set = hnd_set = False

        n_half = len(nodes) // 2

        for rnd in range(1, rounds + 1):
            alive = [n for n in nodes if n.alive]
            if not alive:
                break

            # ── Protocol-specific round ──────────────────────────────────────
            ch_ids, cluster_map = self.select_cluster_heads(alive, rnd, bs)
            pkts = self.run_round(alive, ch_ids, cluster_map, bs, rnd)

            ch_counts.append(len(ch_ids))
            total_packets += pkts

            # ── Update alive status ──────────────────────────────────────────
            dead_now = sum(1 for n in nodes if not n.alive)
            if not fnd_set and dead_now >= 1:
                result.fnd = rnd
                fnd_set = True
            if not hnd_set and dead_now >= n_half:
                result.hnd = rnd
                hnd_set = True

            # ── Per-round stats ───────────────────────────────────────────────
            alive_now = [n for n in nodes if n.alive]
            result.round_stats.append(RoundStats(
                round_num=rnd,
                alive_nodes=len(alive_now),
                dead_nodes=dead_now,
                total_energy=sum(n.energy for n in nodes),
                ch_count=len(ch_ids),
                packets_to_bs=pkts,
            ))

        result.lnd = max((s.round_num for s in result.round_stats
                          if s.alive_nodes == 0), default=rounds)
        result.fnd = result.fnd or result.lnd
        result.hnd = result.hnd or result.lnd

        residuals = [n.energy for n in nodes]
        result.residual_energy_final = sum(residuals)
        result.energy_balance_var = float(
            sum((e - sum(residuals)/len(residuals))**2 for e in residuals) / len(residuals)
            if residuals else 0
        )
        result.total_energy_consumed = (
            sum(n.initial_energy for n in nodes) - result.residual_energy_final
        )
        result.avg_ch_count = sum(ch_counts) / len(ch_counts) if ch_counts else 0
        result.total_packets_bs = total_packets
        result.pdr = total_packets / (rounds * len(nodes)) if rounds * len(nodes) else 0

        return result

    # ── Abstract hooks ────────────────────────────────────────────────────────

    @abstractmethod
    def select_cluster_heads(
        self,
        alive_nodes: List[SensorNode],
        round_num:   int,
        bs:          BaseStation,
    ) -> Tuple[List[int], Dict[int, int]]:
        """Return (ch_node_ids, {member_id: ch_id})."""

    @abstractmethod
    def run_round(
        self,
        alive_nodes: List[SensorNode],
        ch_ids:      List[int],
        cluster_map: Dict[int, int],
        bs:          BaseStation,
        round_num:   int,
    ) -> int:
        """Execute energy dissipation; return packets delivered to BS."""

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _assign_members_to_nearest_ch(
        self,
        alive_nodes: List[SensorNode],
        ch_ids:      List[int],
    ) -> Dict[int, int]:
        """Assign each non-CH node to the closest CH. Empty ch_ids -> empty map."""
        ch_set = set(ch_ids)
        if not ch_set:
            return {}
        ch_nodes = {n.node_id: n for n in alive_nodes if n.node_id in ch_set}
        if not ch_nodes:
            return {}
        cluster_map: Dict[int, int] = {}
        for node in alive_nodes:
            if node.node_id in ch_set:
                cluster_map[node.node_id] = node.node_id
                continue
            best_ch = min(ch_nodes.values(),
                          key=lambda c: node.distance_to(c))
            cluster_map[node.node_id] = best_ch.node_id
        return cluster_map

    def _dissipate_member(self, node: SensorNode, ch: SensorNode) -> None:
        cost = self.em.member_round_energy(self.comm.packet_size,
                                           node.distance_to(ch))
        node.energy -= cost
        if node.energy <= 0:
            node.energy = 0
            node.alive  = False

    def _dissipate_ch(
        self, ch: SensorNode, members: List[SensorNode], bs: BaseStation
    ) -> None:
        n_mem = len(members)
        cost  = self.em.ch_round_energy(
            self.comm.packet_size, n_mem,
            ch.distance_to_point(bs.x, bs.y)
        )
        ch.energy -= cost
        if ch.energy <= 0:
            ch.energy = 0
            ch.alive  = False
