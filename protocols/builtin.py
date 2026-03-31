"""Built-in protocol implementations: LEACH, HEED, PEGASIS, SEP, TEEN."""
from __future__ import annotations
import math, random
from typing import List, Dict, Tuple

from wsn_framework.core.topology import SensorNode, BaseStation
from .base import BaseProtocol


# ── LEACH ─────────────────────────────────────────────────────────────────────

class LEACH(BaseProtocol):
    """Low-Energy Adaptive Clustering Hierarchy."""
    name = "LEACH"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._not_ch_since: Dict[int, int] = {}   # node_id → last CH round
        self._rng = random.Random(42)

    def select_cluster_heads(
        self, alive_nodes, round_num, bs
    ) -> Tuple[List[int], Dict[int, int]]:
        p = self.cfg.ch_ratio
        T_max = 1 / p
        ch_ids = []
        for node in alive_nodes:
            last = self._not_ch_since.get(node.node_id, 0)
            rounds_since = round_num - last
            if rounds_since >= T_max:
                threshold = p / (1 - p * (round_num % int(T_max) or 1))
            else:
                threshold = 0.0
            if self._rng.random() < threshold:
                ch_ids.append(node.node_id)
                self._not_ch_since[node.node_id] = round_num
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        if not ch_ids or not cluster_map:
            return 0
        node_map = {n.node_id: n for n in alive_nodes}
        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members:
                ch_members[cid].append(node_map[nid])
        # members transmit to CH
        for node in alive_nodes:
            ch_id = cluster_map.get(node.node_id)
            if ch_id and ch_id != node.node_id and ch_id in node_map:
                ch_node = node_map[ch_id]
                if ch_node.alive:
                    self._dissipate_member(node, ch_node)
        # CHs aggregate and transmit to BS
        pkts = 0
        for ch_id, members in ch_members.items():
            ch = node_map.get(ch_id)
            if ch and ch.alive:
                self._dissipate_ch(ch, members, bs)
                pkts += 1
        return pkts


# ── HEED ─────────────────────────────────────────────────────────────────────

class HEED(BaseProtocol):
    """Hybrid Energy-Efficient Distributed clustering."""
    name = "HEED"
    default_params = {"ch_ratio": 0.05, "c_prob_min": 0.001}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)

    def select_cluster_heads(
        self, alive_nodes, round_num, bs
    ) -> Tuple[List[int], Dict[int, int]]:
        max_e = max(n.initial_energy for n in alive_nodes)
        ch_ids = []
        for node in alive_nodes:
            ch_prob = self.cfg.ch_ratio * (node.energy / max_e)
            ch_prob = max(ch_prob, self.params["c_prob_min"])
            if self._rng.random() < ch_prob:
                ch_ids.append(node.node_id)
        if not ch_ids and alive_nodes:
            best = max(alive_nodes, key=lambda n: n.energy)
            ch_ids = [best.node_id]
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        return LEACH.run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num)


# ── PEGASIS ───────────────────────────────────────────────────────────────────

class PEGASIS(BaseProtocol):
    """Power-Efficient GAthering in Sensor Information Systems."""
    name = "PEGASIS"
    default_params = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)

    def _build_chain(self, alive_nodes: List[SensorNode]) -> List[SensorNode]:
        if not alive_nodes:
            return []
        remaining = list(alive_nodes)
        chain = [remaining.pop(0)]
        while remaining:
            last = chain[-1]
            nearest = min(remaining, key=lambda n: last.distance_to(n))
            chain.append(nearest)
            remaining.remove(nearest)
        return chain

    def select_cluster_heads(
        self, alive_nodes, round_num, bs
    ) -> Tuple[List[int], Dict[int, int]]:
        if not alive_nodes:
            return [], {}
        chain = self._build_chain(alive_nodes)
        leader_idx = round_num % len(chain)
        leader = chain[leader_idx]
        ch_ids = [leader.node_id]
        cluster_map = {n.node_id: leader.node_id for n in alive_nodes}
        self._chain = chain
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        if not ch_ids or not hasattr(self, "_chain"):
            return 0
        chain = self._chain
        if not chain:
            return 0
        # Each node tx to next neighbor in chain (token passing)
        node_map = {n.node_id: n for n in alive_nodes}
        for i in range(len(chain) - 1):
            src, dst = chain[i], chain[i + 1]
            if src.alive and dst.alive:
                cost = self.em.tx_energy(self.comm.packet_size,
                                         src.distance_to(dst))
                src.energy -= cost
                if src.energy <= 0:
                    src.energy = 0; src.alive = False
                rx_cost = self.em.rx_energy(self.comm.packet_size)
                dst.energy -= rx_cost
                if dst.energy <= 0:
                    dst.energy = 0; dst.alive = False
        # Leader sends to BS
        leader_id = ch_ids[0]
        leader = node_map.get(leader_id)
        if leader and leader.alive:
            dist_bs = leader.distance_to_point(bs.x, bs.y)
            cost = self.em.tx_energy(self.comm.packet_size, dist_bs)
            leader.energy -= cost
            if leader.energy <= 0:
                leader.energy = 0; leader.alive = False
            return 1
        return 0


# ── SEP ───────────────────────────────────────────────────────────────────────

class SEP(BaseProtocol):
    """Stable Election Protocol — handles heterogeneous networks."""
    name = "SEP"
    default_params = {"ch_ratio": 0.05}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._epoch: Dict[int, int] = {}

    def select_cluster_heads(
        self, alive_nodes, round_num, bs
    ) -> Tuple[List[int], Dict[int, int]]:
        p = self.cfg.ch_ratio
        ch_ids = []
        for node in alive_nodes:
            epoch = int(1 / p)
            weighted_p = p * (node.energy / node.initial_energy)
            rnd_in_epoch = round_num % epoch or 1
            threshold = weighted_p / (1 - weighted_p * rnd_in_epoch)
            threshold = max(0.0, threshold)
            if self._rng.random() < threshold:
                ch_ids.append(node.node_id)
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        return LEACH.run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num)


# ── TEEN ──────────────────────────────────────────────────────────────────────

class TEEN(BaseProtocol):
    """Threshold-sensitive Energy Efficient sensor Network."""
    name = "TEEN"
    default_params = {
        "ch_ratio": 0.05,
        "hard_threshold": 0.1,
        "soft_threshold": 0.01,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(42)
        self._not_ch_since: dict = {}

    def select_cluster_heads(self, alive_nodes, round_num, bs):
        p = self.cfg.ch_ratio
        T_max = 1 / p
        ch_ids = []
        for node in alive_nodes:
            last = self._not_ch_since.get(node.node_id, 0)
            rounds_since = round_num - last
            if rounds_since >= T_max:
                threshold = p / (1 - p * (round_num % int(T_max) or 1))
            else:
                threshold = 0.0
            if self._rng.random() < threshold:
                ch_ids.append(node.node_id)
                self._not_ch_since[node.node_id] = round_num
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num) -> int:
        """TEEN: only nodes above threshold transmit, but use full alive_nodes set."""
        if not ch_ids or not cluster_map:
            return 0
        ht = self.params["hard_threshold"]
        st = self.params["soft_threshold"]
        node_map = {n.node_id: n for n in alive_nodes}
        ch_members: Dict[int, List[SensorNode]] = {c: [] for c in ch_ids}
        for nid, cid in cluster_map.items():
            if nid != cid and cid in ch_members and nid in node_map:
                ch_members[cid].append(node_map[nid])
        pkts = 0
        for node in alive_nodes:
            ch_id = cluster_map.get(node.node_id)
            if ch_id and ch_id != node.node_id and ch_id in node_map:
                ch_node = node_map[ch_id]
                if ch_node.alive and node.energy >= max(0, ht - st):
                    self._dissipate_member(node, ch_node)
        for ch_id, members in ch_members.items():
            ch = node_map.get(ch_id)
            if ch and ch.alive:
                self._dissipate_ch(ch, members, bs)
                pkts += 1
        return pkts


# ── Registry ──────────────────────────────────────────────────────────────────

REGISTRY: Dict[str, type] = {
    "LEACH":   LEACH,
    "HEED":    HEED,
    "PEGASIS": PEGASIS,
    "SEP":     SEP,
    "TEEN":    TEEN,
}


def get_protocol(name: str) -> type:
    key = name.upper()
    if key not in REGISTRY:
        raise ValueError(f"Unknown protocol '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[key]


def register(proto_class: type) -> None:
    REGISTRY[proto_class.name.upper()] = proto_class
