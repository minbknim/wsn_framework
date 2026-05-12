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
from .mcp      import MCP, MCP_PLUS

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
