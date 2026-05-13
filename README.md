# WSN 시뮬레이션 프레임워크 v7 (최종 완성판)

## 개요
NS-3·Python 통합 WSN 시뮬레이션 프레임워크.
**19개 프로토콜**, 개선방안 **41개 항목 중 29개 완전 구현(71%)**.

---

## 등록 프로토콜 (19개)

| 분류 | 프로토콜 |
|------|---------|
| 계층형 (5) | LEACH, LEACH-C, HEED, TEEN★, APTEEN |
| 이종계층 (2) | SEP★, DEEC |
| 체인형 (1) | PEGASIS |
| 멀티홉 (1) | EE-LEACH |
| 멀티체인 (5) | MCP★, MCP+★, **AMCP-E★**, **AMCP-E-H2★**, **DMCP★**, AMCP-E-RL★ |
| 데이터중심 (2) | SPIN, RUMOR★ |
| 위치기반 (2) | GEAR★, GAF★ |

★=최종판에서 개선 / **굵게**=제안 프로토콜 / 밑줄=신규

---

## 신규 구현 16개 (v5→v7)

| # | 항목 | 파일 |
|---|------|------|
| 1 | log-normal shadowing 채널 모델 | `core/energy.py` |
| 2 | 에너지 하베스팅 (태양광 sin²) | `core/energy.py` + `base.py` |
| 3 | 모바일 BS (UAV 궤적) | `core/topology.py` |
| 4 | 3D 좌표·거리 | `core/topology.py` |
| 5 | MCP 예비 링크/백업 경로 | `protocols/mcp.py` |
| 6 | 체인 길이 균등 분배 | `protocols/mcp.py` |
| 7 | 적응형 가중치 w_dist/w_energy | `protocols/mcp.py`, `amcp_e.py` |
| 8 | 임계값 기반 하이브리드 차분전송 | `protocols/amcp_e.py` |
| 9 | TDMA 슬롯 스케줄링 | `protocols/base.py` |
| 10 | AMCP-E-H2 (2-tier 하이브리드) | `protocols/amcp_e_h2.py` |
| 11 | DMCP (분산형 그리디 체인) | `protocols/dmcp.py` |
| 12 | AMCP-E-RL DQN v4 | `protocols/amcp_e_rl.py` |
| 13 | 병렬 실험 엔진 | `experiment/parallel_experiment.py` |
| 14 | PSO 노드 위치 최적화 | `utils/swarm_optimizer.py` |
| 15 | IoT-SEC 보안 에너지 추상화 | `utils/security_model.py` |
| 16 | Welch t-검정 + Bootstrap CI | `experiment/metrics.py` |

---

## 최종 실험 결과 (Score=LND×PDR 기준)

| 순위 | 프로토콜 | LND | PDR | Score |
|------|---------|-----|-----|-------|
| **1위 ★** | **AMCP-E** | 69,555±2,915 | 1.679 | **116,783** |
| **2위 ★** | **AMCP-E-H2** | ≥1,000,000 | 0.102 | **102,400** |
| 3위 | GEAR | 12,892±1,030 | 4.990 | 64,332 |
| 4위 | LEACH | 38,490±2,308 | 1.651 | 63,534 |
| 최하위⚠ | TEEN | 126,486 | 0.001 | 76 |

> ⚠️ TEEN은 LND 1위이나 PDR=0.001 → Score=76 (최하위)  
> **LND 단독 지표의 편향**: TEEN이 데이터를 거의 전달하지 않아 에너지 소모가 극히 적음

---

## 커버리지 요약

| 상태 | 수 | 비율 |
|------|---|------|
| ✅ 완전 구현 | 29개 | 71% |
| ⚠️ 부분 구현 | 1개 | 3% |
| 🔵 시뮬 불필요 | 8개 | 20% |
| 🟢 차후 연구 | 3개 | 7% |

---

## 주요 API

```python
# 기본 실험
from wsn_framework.protocols import get_protocol
proto = get_protocol("AMCP-E")(cfg.protocol, em, cfg.comm)
result = proto.run(topo, 1_000_000, seed=42, run_until_dead=True)

# 채널 모델
from wsn_framework.core.energy import EnergyConfig, EnergyModel
ec  = EnergyConfig(shadowing_std=4.0)   # log-normal shadowing
em  = EnergyModel(ec)

# 에너지 하베스팅
ec2 = EnergyConfig(harvesting=True, harvest_rate=0.001, harvest_period=500)

# 모바일 BS (UAV)
from wsn_framework.core.topology import BaseStation
bs = BaseStation(x=50, y=50, trajectory=[(50,50),(60,40),(70,30)])

# PSO 최적화
from wsn_framework.utils.swarm_optimizer import PSOOptimizer
pso = PSOOptimizer(n_nodes=100, n_particles=20, n_iter=50)
best_positions = pso.optimize()  # 개선율 ~40%

# 보안 에너지
from wsn_framework.utils.security_model import SecurityModel, SecurityConfig
sec = SecurityModel(SecurityConfig(enabled=True))
overhead = sec.tx_overhead(4000)  # AES+HMAC 오버헤드

# 병렬 실험
from wsn_framework.experiment.parallel_experiment import ParallelExperiment
exp = ParallelExperiment("configs/default_scenario.yaml", n_workers=4)
result = exp.run("AMCP-E", n_nodes=500, repetitions=10)
result = exp.scalability_test("AMCP-E", node_counts=[100,200,500,1000])

# 통계 검증
from wsn_framework.experiment.metrics import pairwise_ttest, bootstrap_ci
lo, hi = bootstrap_ci(lnd_values, n_boot=400, ci=0.95)
```

---

## 에너지 모델 파라미터

```
영역: 100×100m², N=100, BS=(50,50)m
E��=0.5J, E_elec=50nJ/bit, ε_fs=10pJ/bit/m², ε_mp=0.0013pJ/bit/m⁴
E_agg=5nJ/bit, 패킷=4000bits, 제어=200bits
shadowing_std=4.0dB (현실적 채널), harvest_rate=0.0001J/round
```

---

## 저자
민복기, 박지수, 손진곤  
한국방송통신대학교 / 전주대학교 | 2026
