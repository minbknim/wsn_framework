"""
security_model.py — IoT-SEC 보안 에너지 추상화

보안 기능의 에너지 오버헤드를 파라미터로 추상화하여
실제 암호화 없이도 보안 비용을 시뮬레이션에 반영
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SecurityConfig:
    """보안 설정 파라미터."""
    enabled:         bool  = False
    # 암호화 에너지 오버헤드 (J/bit)
    e_encrypt:       float = 5e-9    # AES-GCM 기준
    e_decrypt:       float = 4e-9
    e_mac:           float = 2e-9    # HMAC-SHA256
    e_sign:          float = 10e-9   # ECDSA
    # 적용 범위
    encrypt_data:    bool  = True    # 데이터 패킷 암호화
    authenticate:    bool  = True    # HMAC 인증
    sign_routing:    bool  = False   # 라우팅 메시지 서명 (선택)
    # 키 갱신
    key_refresh_interval: int = 1000  # 라운드


class SecurityModel:
    """
    보안 에너지 오버헤드 계산기.

    실제 암호화 없이 에너지 비용만 파라미터로 반영.
    """

    def __init__(self, cfg: SecurityConfig = None):
        self.cfg = cfg or SecurityConfig()

    def tx_overhead(self, bits: int) -> float:
        """전송 시 보안 오버헤드 (암호화 + MAC)."""
        if not self.cfg.enabled: return 0.0
        e = 0.0
        if self.cfg.encrypt_data:
            e += bits * self.cfg.e_encrypt
        if self.cfg.authenticate:
            e += bits * self.cfg.e_mac
        return e

    def rx_overhead(self, bits: int) -> float:
        """수신 시 보안 오버헤드 (복호화 + MAC 검증)."""
        if not self.cfg.enabled: return 0.0
        e = 0.0
        if self.cfg.encrypt_data:
            e += bits * self.cfg.e_decrypt
        if self.cfg.authenticate:
            e += bits * self.cfg.e_mac
        return e

    def routing_overhead(self, bits: int) -> float:
        """라우팅 메시지 서명 오버헤드 (선택적)."""
        if not self.cfg.enabled or not self.cfg.sign_routing: return 0.0
        return bits * self.cfg.e_sign

    def key_refresh_cost(self, n_nodes: int) -> float:
        """키 갱신 비용 (key_refresh_interval 라운드마다)."""
        if not self.cfg.enabled: return 0.0
        # 각 노드가 인접 노드와 키 교환 (ECDH 기준)
        return n_nodes * 50e-9   # ECDH per node

    def overhead_ratio(self, base_tx: float, bits: int) -> float:
        """기본 TX 에너지 대비 보안 오버헤드 비율."""
        if base_tx <= 0: return 0.0
        return self.tx_overhead(bits) / base_tx
