"""ScenarioConfig — all simulation parameters in one place."""
from __future__ import annotations
import copy, random, uuid
from dataclasses import dataclass, field, asdict
from typing import Tuple, List, Optional
import yaml


# ── Sub-configs ───────────────────────────────────────────────────────────────

@dataclass
class TopologyConfig:
    area_width:   float = 100.0        # m
    area_height:  float = 100.0        # m
    num_nodes:    int   = 100
    deployment:   str   = "random"     # random | grid | uniform
    bs_position:  Tuple[float, float] = (50.0, 50.0)
    mobility:     str   = "static"     # static | mobile
    mobile_speed: float = 0.0          # m/s (if mobile)


@dataclass
class EnergyConfig:
    initial_energy: float = 0.5        # J
    e_elec:         float = 50e-9      # J/bit  (circuit energy)
    e_amp_fs:       float = 100e-12    # J/bit/m²  (free-space)
    e_amp_mp:       float = 0.0013e-12 # J/bit/m⁴  (multipath)
    e_agg:          float = 5e-9       # J/bit/signal (aggregation)
    heterogeneous:  bool  = False
    # heterogeneous settings
    het_levels:     int   = 2          # number of energy tiers
    het_ratios:     List[float] = field(default_factory=lambda: [1.0, 2.0])
    het_fractions:  List[float] = field(default_factory=lambda: [0.8, 0.2])


@dataclass
class CommConfig:
    tx_range:          float = 100.0   # m  max transmission range
    packet_size:       int   = 4000    # bits
    ctrl_packet_size:  int   = 200     # bits
    channel_model:     str   = "first_order"  # first_order | rayleigh
    mac_protocol:      str   = "TDMA"


@dataclass
class ProtocolConfig:
    name:     str   = "LEACH"
    ch_ratio: float = 0.05
    routing:  str   = "single_hop"     # single_hop | multi_hop
    params:   dict  = field(default_factory=dict)


@dataclass
class SimConfig:
    rounds:      int  = 2000
    repetitions: int  = 100
    seed:        int  = 42
    parallel:    bool = True
    n_jobs:      int  = -1             # -1 = all CPU cores


# ── Top-level config ──────────────────────────────────────────────────────────

@dataclass
class ScenarioConfig:
    topology:   TopologyConfig  = field(default_factory=TopologyConfig)
    energy:     EnergyConfig    = field(default_factory=EnergyConfig)
    comm:       CommConfig      = field(default_factory=CommConfig)
    protocol:   ProtocolConfig  = field(default_factory=ProtocolConfig)
    simulation: SimConfig       = field(default_factory=SimConfig)
    run_id:     str             = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # ── Factory ──────────────────────────────────────────────────────────────
    @classmethod
    def from_yaml(cls, path: str) -> "ScenarioConfig":
        with open(path) as f:
            raw = yaml.safe_load(f)
        cfg = cls()
        if "topology"   in raw: cfg.topology   = TopologyConfig(**raw["topology"])
        if "energy"     in raw: cfg.energy      = EnergyConfig(**raw["energy"])
        if "comm"       in raw: cfg.comm        = CommConfig(**raw["comm"])
        if "protocol"   in raw: cfg.protocol    = ProtocolConfig(**raw["protocol"])
        if "simulation" in raw: cfg.simulation  = SimConfig(**raw["simulation"])
        cfg.topology.bs_position = tuple(cfg.topology.bs_position)
        return cfg

    def to_yaml(self, path: str) -> None:
        import copy
        data = asdict(self)
        # tuple → list (safe_load 호환)
        if "topology" in data and "bs_position" in data["topology"]:
            data["topology"]["bs_position"] = list(data["topology"]["bs_position"])
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def clone_for_protocol(self, protocol_name: str) -> "ScenarioConfig":
        """동일 환경에서 프로토콜만 교체한 복사본 반환."""
        c = copy.deepcopy(self)
        c.protocol.name = protocol_name
        c.run_id = uuid.uuid4().hex[:8]
        return c

    def validate(self) -> bool:
        assert self.topology.num_nodes > 0, "num_nodes must be > 0"
        assert self.energy.initial_energy > 0, "initial_energy must be > 0"
        assert self.simulation.rounds > 0, "rounds must be > 0"
        assert self.simulation.repetitions > 0, "repetitions must be > 0"
        assert 0 < self.protocol.ch_ratio < 1, "ch_ratio must be in (0, 1)"
        return True
