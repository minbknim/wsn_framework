"""Simulation result dataclasses."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class RoundStats:
    round_num:       int
    alive_nodes:     int
    dead_nodes:      int
    total_energy:    float
    ch_count:        int
    packets_to_bs:   int


@dataclass
class ExperimentResult:
    protocol:       str
    seed:           int
    repetition_id:  int

    # Network lifetime
    fnd:   int = 0   # First Node Dead  (round)
    hnd:   int = 0   # Half Node Dead
    lnd:   int = 0   # Last Node Dead

    # Energy
    total_energy_consumed: float = 0.0
    residual_energy_final: float = 0.0
    energy_balance_var:    float = 0.0   # variance of residual energies

    # QoS
    pdr:              float = 0.0   # Packet Delivery Ratio
    e2e_delay_ms:     float = 0.0
    throughput_bps:   float = 0.0
    total_packets_bs: int   = 0

    # Clustering
    avg_ch_count: float = 0.0

    # Per-round time series (for plots)
    round_stats: List[RoundStats] = field(default_factory=list)


@dataclass
class AggregatedResult:
    """Statistics over multiple Monte-Carlo repetitions."""
    protocol:      str
    repetitions:   int

    fnd_mean:   float = 0.0;  fnd_std:   float = 0.0
    hnd_mean:   float = 0.0;  hnd_std:   float = 0.0
    lnd_mean:   float = 0.0;  lnd_std:   float = 0.0

    pdr_mean:   float = 0.0;  pdr_std:   float = 0.0
    e_bal_mean: float = 0.0;  e_bal_std: float = 0.0
    e_consumed_mean: float = 0.0
    avg_ch_mean: float = 0.0

    raw: List[ExperimentResult] = field(default_factory=list)
