"""
BaseProtocol — WSN 프로토콜 공통 기반 클래스 (최종 개선판 v3)

개선사항:
  ① PDR = total_packets / max(lnd, 1)  (라운드당 평균 BS 도달 패킷)
  ② _consume() 원자적 에너지 소모 (음수 방지 전역 통일)
  ③ _dissipate_ctrl() — 제어패킷(ADV/REQ) 에너지 반영
  ④ model_idle 파라미터 — 슬립 노드 아이들 에너지 선택적 반영
  ⑤ _dissipate_member() / _dissipate_ch() 공통 강화
"""
from __future__ import annotations

import random, math
from abc import abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wsn_framework.core.energy import EnergyModel
from wsn_framework.core.result import ExperimentResult, RoundStats
from wsn_framework.core.topology import BaseStation, SensorNode, TopologyManager


class BaseCommConfig:
    def __init__(self):
        self.packet_size      = 4000
        self.ctrl_packet_size = 200


class BaseProtocolConfig:
    def __init__(self):
        self.ch_ratio = 0.05
        self.rounds   = 2000


class BaseProtocol:
    """모든 WSN 프로토콜의 공통 베이스."""
    name: str = "Base"
    default_params: dict = {}

    def __init__(self, cfg, em: EnergyModel, comm):
        self.cfg   = cfg
        self.em    = em
        self.comm  = comm
        self.params = dict(self.default_params)

    # ── ① 원자적 에너지 소모 ─────────────────────────────────────────────────
    @staticmethod
    def _consume(node: SensorNode, cost: float) -> bool:
        """에너지 소모 + 음수 방지 + 사망 처리. 반환: True=생존"""
        node.energy = max(0.0, node.energy - cost)
        if node.energy == 0.0:
            node.alive = False
        return node.alive

    # ── ③ 제어패킷 에너지 반영 ───────────────────────────────────────────────
    def _dissipate_ctrl(self, node: SensorNode, distance: float) -> bool:
        """제어패킷(ADV/REQ) TX 에너지 소모."""
        cost = self.em.tx_energy(self.comm.ctrl_packet_size, distance)
        return self._consume(node, cost)

    def _recv_ctrl(self, node: SensorNode) -> bool:
        """제어패킷 RX 에너지 소모."""
        cost = self.em.rx_energy(self.comm.ctrl_packet_size)
        return self._consume(node, cost)

    # ── ⑤ 멤버→CH 전송 ───────────────────────────────────────────────────────
    def _dissipate_member(self, member: SensorNode, ch: SensorNode) -> bool:
        """멤버 노드 → CH 전송. 반환: True=전송 성공"""
        if not member.alive or not ch.alive:
            return False
        pkt = self.comm.packet_size
        d   = member.distance_to(ch)
        if not self._consume(member, self.em.tx_energy(pkt, d)):
            return False
        self._consume(ch, self.em.rx_energy(pkt))
        return ch.alive

    # ── CH 집계 + BS 전송 ─────────────────────────────────────────────────────
    def _dissipate_ch(self, ch: SensorNode, members: List[SensorNode],
                     bs: BaseStation, pkt: Optional[int] = None) -> bool:
        """CH 집계 + BS 전송. 반환: True=전송 성공"""
        if not ch.alive:
            return False
        if pkt is None:
            pkt = self.comm.packet_size
        n_mem = len(members)
        if not self._consume(ch, self.em.agg_energy(pkt * (n_mem + 1))):
            return False
        d_bs = ch.distance_to_point(bs.x, bs.y)
        return self._consume(ch, self.em.tx_energy(pkt, d_bs))

    # ── 가장 가까운 CH에 멤버 배정 ───────────────────────────────────────────
    def _assign_members_to_nearest_ch(self, alive_nodes: List[SensorNode],
                                       ch_ids: List[int]) -> Dict[int, int]:
        if not ch_ids:
            return {}
        nm = {n.node_id: n for n in alive_nodes}
        ch_nodes = [nm[c] for c in ch_ids if c in nm]
        cluster_map: Dict[int, int] = {}
        for node in alive_nodes:
            if node.node_id in ch_ids:
                cluster_map[node.node_id] = node.node_id
            else:
                nearest = min(ch_nodes, key=lambda c: node.distance_to(c))
                cluster_map[node.node_id] = nearest.node_id
        return cluster_map

    # ── ④ 슬립 노드 아이들 에너지 (선택적) ───────────────────────────────────
    def _apply_idle_energy(self, alive_nodes: List[SensorNode],
                            ch_ids: List[int]) -> None:
        """
        model_idle=True 시 비Active 노드에 소량 아이들 에너지 차감.
        E_idle = E_elec × ctrl_bits × idle_factor (기본 0.5%)
        """
        if not self.params.get("model_idle", False):
            return
        idle_factor = self.params.get("idle_factor", 0.005)
        ctrl = self.comm.ctrl_packet_size
        idle_cost = self.em.cfg.e_elec * ctrl * idle_factor
        ch_set = set(ch_ids)
        for node in alive_nodes:
            if node.node_id not in ch_set:
                self._consume(node, idle_cost)

    # ── 추상 메서드 ───────────────────────────────────────────────────────────
    @abstractmethod
    def select_cluster_heads(self, alive_nodes, round_num, bs): ...

    @abstractmethod
    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int: ...

    # ── 메인 실행 루프 ────────────────────────────────────────────────────────
    def run(self, topology: TopologyManager, max_rounds: int, seed: int,
            repetition_id: int, run_until_dead: bool = False,
            save_topo_changes: bool = False, topo_save_interval: int = 500,
            save_dir: Optional[Path] = None) -> ExperimentResult:

        nodes = topology.nodes
        bs    = topology.bs
        result = ExperimentResult(
            protocol=self.name, seed=seed, repetition_id=repetition_id)
        total_packets = 0
        n_half = len(nodes) // 2

        for rnd in range(1, max_rounds + 1):
            alive = [n for n in nodes if n.alive]
            if not alive:
                break

            dead_now = len(nodes) - len(alive)
            if dead_now >= 1 and result.fnd == 0:
                result.fnd = rnd
            if dead_now >= n_half and result.hnd == 0:
                result.hnd = rnd
            result.lnd = rnd

            ch_ids, cluster_map = self.select_cluster_heads(alive, rnd, bs)

            # ④ 슬립 에너지 반영 (model_idle=True 시)
            self._apply_idle_energy(alive, ch_ids)

            pkts = self.run_round(alive, ch_ids, cluster_map, bs, rnd)
            total_packets += pkts

            e_total = sum(n.energy for n in nodes)
            result.round_stats.append(RoundStats(
                round_num=rnd, alive_nodes=len(alive), dead_nodes=dead_now,
                total_energy=e_total, ch_count=len(ch_ids), packets_to_bs=pkts))

            if save_topo_changes and save_dir and rnd % topo_save_interval == 0:
                self._save_topology_frame(topology, ch_ids, cluster_map,
                                          rnd, save_dir, len(alive))

            if run_until_dead and not alive:
                break

        result.total_energy_consumed = sum(
            n.initial_energy - n.energy for n in nodes)
        residual = [n.energy for n in nodes]
        result.residual_energy_final = sum(residual)
        if len(residual) > 1:
            mean_r = result.residual_energy_final / len(residual)
            result.energy_balance_var = sum(
                (e - mean_r) ** 2 for e in residual) / len(residual)

        result.total_packets_bs = total_packets
        result.avg_ch_count = (
            sum(s.ch_count for s in result.round_stats) / len(result.round_stats)
            if result.round_stats else 0)

        # ① 개선된 PDR: 라운드당 평균 BS 도달 패킷 수
        result.pdr = total_packets / max(result.lnd, 1)
        return result

    @staticmethod
    def _save_topology_frame(topology, ch_ids, cluster_map,
                              round_num, save_dir, alive_count):
        save_dir.mkdir(parents=True, exist_ok=True)
        try:
            import matplotlib; matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.set_xlim(-5,105); ax.set_ylim(-5,105); ax.set_aspect("equal")
            ax.set_title(f"Round {round_num} | alive={alive_count}", fontsize=9)
            nm = {n.node_id: n for n in topology.nodes}
            ch_set = set(ch_ids)
            for node in topology.nodes:
                if not node.alive:
                    ax.plot(node.x, node.y, "x", color="gray", alpha=0.3, markersize=4)
                elif node.node_id in ch_set:
                    ax.plot(node.x, node.y, "r^", markersize=6)
                else:
                    cid = cluster_map.get(node.node_id)
                    ax.plot(node.x, node.y, ".", color="steelblue",
                            markersize=4, alpha=0.7)
                    if cid and cid in nm and cid != node.node_id:
                        ch = nm[cid]
                        ax.plot([node.x,ch.x],[node.y,ch.y],
                                color="steelblue",alpha=0.15,linewidth=0.5)
            ax.plot(topology.bs.x, topology.bs.y, "k*", markersize=12)
            fname = (save_dir /
                     f"round_{round_num:06d}_alive{alive_count}.png")
            fig.savefig(str(fname), dpi=80, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            pass
