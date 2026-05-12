"""builtin.py — 하위 호환성 유지 레이어. 신규 코드는 개별 모듈 사용 권장."""
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
from .__init__ import REGISTRY, get_protocol, register, list_protocols

__all__ = [
    "LEACH","LEACH_C","HEED","PEGASIS","TEEN",
    "APTEEN","SEP","DEEC","EE_LEACH","MCP","MCP_PLUS",
    "REGISTRY","get_protocol","register","list_protocols",
]
