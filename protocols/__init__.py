"""WSN 프로토콜 플러그인 패키지 — 11개 프로토콜."""
from .base import BaseProtocol

from .leach    import LEACH
from .leach_c  import LEACH_C
from .heed     import HEED
from .pegasis  import PEGASIS
from .teen     import TEEN
from .apteen   import APTEEN
from .sep      import SEP
from .deec     import DEEC
from .ee_leach import EE_LEACH
from .mcp          import MCP, MCP_PLUS
from .amcp_e       import AMCP_E
from .amcp_e_rl    import AMCP_E_RL
from .spin         import SPIN
from .rumor_routing import RumorRouting
from .gear         import GEAR
from .gaf          import GAF

REGISTRY: dict = {
    "LEACH":    LEACH,
    "LEACH-C":  LEACH_C,
    "HEED":     HEED,
    "PEGASIS":  PEGASIS,
    "TEEN":     TEEN,
    "APTEEN":   APTEEN,
    "SEP":      SEP,
    "DEEC":     DEEC,
    "EE-LEACH": EE_LEACH,
    "MCP":      MCP,
    "MCP+":     MCP_PLUS,
    "AMCP-E":   AMCP_E,
    "AMCP-E-RL": AMCP_E_RL,
    # 신규 추가 (MCP 논문 참조 프로토콜)
    "SPIN":     SPIN,
    "RUMOR":    RumorRouting,
    "GEAR":     GEAR,
    "GAF":      GAF,
}

def get_protocol(name: str) -> type:
    key = name.upper().replace("_", "-")
    if key not in REGISTRY:
        raise ValueError(f"Unknown protocol '{name}'. Available: {sorted(REGISTRY.keys())}")
    return REGISTRY[key]

def register(proto_class: type) -> None:
    REGISTRY[proto_class.name.upper()] = proto_class

def list_protocols() -> list:
    return sorted(REGISTRY.keys())

from .amcp_e_h2 import AMCP_E_H2
REGISTRY['AMCP-E-H2'] = AMCP_E_H2

from .dmcp import DMCP
REGISTRY['DMCP'] = DMCP
