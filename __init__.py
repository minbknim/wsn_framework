"""WSN Framework — NS3 + Python unified simulation environment."""
__version__ = "1.0.0"

from wsn_framework.framework import WSNFramework
from wsn_framework.core.config import ScenarioConfig
from wsn_framework.protocols.builtin import REGISTRY, get_protocol, register
