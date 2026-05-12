"""Abstract base class for all WSN routing protocols."""
from __future__ import annotations
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from wsn_framework.core.topology import SensorNode, BaseStation, TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.core.config import ProtocolConfig, CommConfig
from wsn_framework.core.result import ExperimentResult, RoundStats


class BaseProtocol(ABC):
    name: str = "BASE"
    default_params: dict = {}

    def __init__(self, proto_cfg, energy_model, comm_cfg):
        self.cfg = proto_cfg
        self.em = energy_model
        self.comm = comm_cfg
        self.params = {**self.default_params, **proto_cfg.params}

    def run(
        self,
        topology,
        rounds: int,
        seed: int,
        rep_id: int,
        run_until_dead: bool = False,
        topo_save_dir=None,
        topo_save_interval: int = 50,
    ):
        """
        시뮬레이션 실행.

        Parameters
        ----------
        run_until_dead    : True → 모든 노드 사망 시까지 무한 반복
        topo_save_dir     : 토폴로지 그림 저장 폴더 (None=저장 안 함)
        topo_save_interval: 몇 라운드마다 강제 저장 (0=비활성, 기본 50)
                            interval>0이면 interval 기준으로만 저장
                            (매 라운드 CH 변화 감지로 과도한 저장 방지)
        """
        nodes = topology.nodes
        bs = topology.bs
        result = ExperimentResult(protocol=self.name, seed=seed, repetition_id=rep_id)
        total_packets = 0
        ch_counts = []
        fnd_set = hnd_set = False
        n_half = len(nodes) // 2
        prev_alive_count = len(nodes)
        topo_saved_rounds = set()
        max_rounds = 10_000_000 if run_until_dead else rounds

        for rnd in range(1, max_rounds + 1):
            alive = [n for n in nodes if n.alive]
            if not alive:
                break

            ch_ids, cluster_map = self.select_cluster_heads(alive, rnd, bs)
            pkts = self.run_round(alive, ch_ids, cluster_map, bs, rnd)
            ch_counts.append(len(ch_ids))
            total_packets += pkts

            dead_now = sum(1 for n in nodes if not n.alive)
            alive_now = len(nodes) - dead_now

            if not fnd_set and dead_now >= 1:
                result.fnd = rnd; fnd_set = True
            if not hnd_set and dead_now >= n_half:
                result.hnd = rnd; hnd_set = True

            result.round_stats.append(RoundStats(
                round_num=rnd, alive_nodes=alive_now, dead_nodes=dead_now,
                total_energy=sum(n.energy for n in nodes),
                ch_count=len(ch_ids), packets_to_bs=pkts,
            ))

            # 토폴로지 저장: interval 기준으로만 (과도한 저장 방지)
            if topo_save_dir is not None and topo_save_interval > 0:
                # interval 저장
                if rnd % topo_save_interval == 0 and rnd not in topo_saved_rounds:
                    self._save_topology_frame(
                        topology, ch_ids, cluster_map,
                        rnd, Path(topo_save_dir), alive_now)
                    topo_saved_rounds.add(rnd)
                # 노드 사망 시 추가 저장 (중요 이벤트)
                elif alive_now < prev_alive_count and rnd not in topo_saved_rounds:
                    self._save_topology_frame(
                        topology, ch_ids, cluster_map,
                        rnd, Path(topo_save_dir), alive_now)
                    topo_saved_rounds.add(rnd)

            prev_alive_count = alive_now
            if not run_until_dead and rnd >= rounds:
                break

        # 결과 집계
        lnd_cands = [s.round_num for s in result.round_stats if s.alive_nodes == 0]
        result.lnd = lnd_cands[0] if lnd_cands else (
            result.round_stats[-1].round_num if result.round_stats else rounds)
        result.fnd = result.fnd or result.lnd
        result.hnd = result.hnd or result.lnd

        residuals = [n.energy for n in nodes]
        result.residual_energy_final = sum(residuals)
        n_nodes = len(residuals)
        avg_r = sum(residuals) / n_nodes if n_nodes else 0
        result.energy_balance_var = (
            sum((e - avg_r)**2 for e in residuals) / n_nodes if n_nodes else 0)
        result.total_energy_consumed = (
            sum(n_.initial_energy for n_ in nodes) - result.residual_energy_final)
        result.avg_ch_count = sum(ch_counts) / len(ch_counts) if ch_counts else 0
        result.total_packets_bs = total_packets
        total_ops = len(result.round_stats) * len(nodes)
        result.pdr = total_packets / total_ops if total_ops else 0
        return result

    @staticmethod
    def _save_topology_frame(topology, ch_ids, cluster_map, round_num, save_dir, alive_count):
        save_dir.mkdir(parents=True, exist_ok=True)
        total = len(topology.nodes)
        dead = total - alive_count
        fname = save_dir / f"round_{round_num:06d}_alive{alive_count}_dead{dead}.png"
        try:
            topology.visualize(
                output_path=fname,
                title=f"Round {round_num}  |  Alive:{alive_count}/{total}  Dead:{dead}",
                ch_ids=ch_ids, cluster_map=cluster_map,
                round_num=round_num, show_links=False, dpi=80)
        except Exception:
            pass

    @abstractmethod
    def select_cluster_heads(self, alive_nodes, round_num, bs): ...

    @abstractmethod
    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int: ...

    def _assign_members_to_nearest_ch(self, alive_nodes, ch_ids):
        ch_set = set(ch_ids)
        if not ch_set: return {}
        ch_nodes = {n.node_id: n for n in alive_nodes if n.node_id in ch_set}
        if not ch_nodes: return {}
        cluster_map = {}
        for node in alive_nodes:
            if node.node_id in ch_set:
                cluster_map[node.node_id] = node.node_id
                continue
            best = min(ch_nodes.values(), key=lambda c: node.distance_to(c))
            cluster_map[node.node_id] = best.node_id
        return cluster_map

    def _dissipate_member(self, node, ch):
        cost = self.em.member_round_energy(self.comm.packet_size, node.distance_to(ch))
        node.energy -= cost
        if node.energy <= 0: node.energy = 0; node.alive = False

    def _dissipate_ch(self, ch, members, bs):
        cost = self.em.ch_round_energy(
            self.comm.packet_size, len(members), ch.distance_to_point(bs.x, bs.y))
        ch.energy -= cost
        if ch.energy <= 0: ch.energy = 0; ch.alive = False
