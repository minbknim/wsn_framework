"""NS3Bridge — generates NS-3 C++ simulation scripts and runs them."""
from __future__ import annotations
import logging
import os
import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from wsn_framework.core.config import ScenarioConfig
from wsn_framework.core.result import RoundStats

log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class RawSimEvent:
    time:       float
    event_type: str   # "tx" | "rx" | "drop"
    node_id:    int
    packet_size: int


@dataclass
class NS3RawResult:
    run_id:     str
    events:     List[RawSimEvent] = field(default_factory=list)
    stdout:     str = ""
    stderr:     str = ""
    returncode: int = 0


class NS3Bridge:
    """
    Two operation modes:
      1. NATIVE  — calls ns3 binary (requires NS3 installed, used inside Docker)
      2. PYTHON  — pure-Python energy simulation (fallback / testing mode)

    Mode is auto-detected: if NS3_PATH env var is set AND the binary exists,
    NATIVE mode is used. Otherwise PYTHON mode.
    """

    def __init__(
        self,
        ns3_path:   Optional[str] = None,
        script_dir: Optional[str] = None,
        mode:       str = "auto",   # "auto" | "native" | "python"
    ):
        self.ns3_path   = Path(ns3_path or os.getenv("NS3_PATH", "/opt/ns3"))
        self.script_dir = Path(script_dir or "/tmp/wsn_scripts")
        self.script_dir.mkdir(parents=True, exist_ok=True)

        if mode == "auto":
            binary = self.ns3_path / "ns3"
            self._mode = "native" if binary.exists() else "python"
        else:
            self._mode = mode

        log.info(f"NS3Bridge mode: {self._mode}")

        # Jinja2 env for C++ template rendering
        self._jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def mode(self) -> str:
        return self._mode

    # ── Script generation ─────────────────────────────────────────────────────

    def generate_script(self, cfg: ScenarioConfig) -> Path:
        """Render wsn_base.cc.j2 → a .cc file ready for ns3 run."""
        tpl = self._jinja.get_template("wsn_base.cc.j2")
        rendered = tpl.render(
            run_id           = cfg.run_id,
            num_nodes        = cfg.topology.num_nodes,
            area_x           = cfg.topology.area_width,
            area_y           = cfg.topology.area_height,
            bs_x             = cfg.topology.bs_position[0],
            bs_y             = cfg.topology.bs_position[1],
            tx_range         = cfg.comm.tx_range,
            initial_energy   = cfg.energy.initial_energy,
            e_elec           = cfg.energy.e_elec,
            e_amp_fs         = cfg.energy.e_amp_fs,
            e_amp_mp         = cfg.energy.e_amp_mp,
            packet_size      = cfg.comm.packet_size,
            ctrl_packet_size = cfg.comm.ctrl_packet_size,
            rounds           = cfg.simulation.rounds,
            seed             = cfg.simulation.seed,
            protocol         = cfg.protocol.name,
            ch_ratio         = cfg.protocol.ch_ratio,
        )
        path = self.script_dir / f"wsn_{cfg.run_id}.cc"
        path.write_text(rendered)
        log.debug(f"NS3 script written → {path}")
        return path

    # ── Native NS3 execution ──────────────────────────────────────────────────

    def run_native(self, script: Path, timeout: int = 300) -> NS3RawResult:
        """Compile and run the generated C++ script via ns3 binary."""
        binary = self.ns3_path / "ns3"
        cmd = [str(binary), "run", str(script), "--no-build"]
        log.info(f"Running NS3: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd, cwd=str(self.ns3_path),
                capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            log.error("NS3 simulation timed out")
            return NS3RawResult(run_id=script.stem, returncode=-1)

        result = NS3RawResult(
            run_id=script.stem,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
        if proc.returncode != 0:
            log.warning(f"NS3 exited with code {proc.returncode}")
        else:
            # Parse trace output lines: "TIME NODE_ID EVENT PKT_SIZE"
            for line in proc.stdout.splitlines():
                ev = self._parse_trace_line(line)
                if ev:
                    result.events.append(ev)
        return result

    @staticmethod
    def _parse_trace_line(line: str) -> Optional[RawSimEvent]:
        # Expected format: "1.234 42 tx 4000"
        m = re.match(r"^([\d.]+)\s+(\d+)\s+(tx|rx|drop)\s+(\d+)", line.strip())
        if m:
            return RawSimEvent(
                time=float(m.group(1)),
                event_type=m.group(3),
                node_id=int(m.group(2)),
                packet_size=int(m.group(4)),
            )
        return None

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self, run_id: str) -> None:
        for suffix in [".cc", ".tr", ".pcap"]:
            f = self.script_dir / f"wsn_{run_id}{suffix}"
            if f.exists():
                f.unlink()
