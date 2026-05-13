# WSN 시뮬레이션 프레임워크 v7 (최종 완성판)

NS-3·Python 통합 WSN 시뮬레이션 프레임워크. **19개 프로토콜**, 개선방안 **41개 항목 중 29개 완전 구현(71%)**.

> 논문: *WSN MCP 개선방안 41개 완전 구현 및 검증 — Framework v7* (KIPS, 2026.05)  
> 저자: 민복기, 박지수, 손진곤 (한국방송통신대학교 / 전주대학교)

---

## 등록 프로토콜 (19개)

| 분류 | 프로토콜 |
|---|---|
| 계층형 (5) | LEACH, LEACH-C, HEED, TEEN★, APTEEN |
| 이종계층 (2) | SEP★, DEEC |
| 체인형 (1) | PEGASIS |
| 멀티홉 (1) | EE-LEACH |
| 멀티체인 (6) | MCP★, MCP+★, **AMCP-E★**, **AMCP-E-H2★**, AMCP-E-RL★†, **DMCP★** |
| 데이터중심 (2) | SPIN, RUMOR★ |
| 위치기반 (2) | GEAR★, GAF★ |

★=최종판에서 개선·신규 구현  /  **굵게**=제안 프로토콜

> † **AMCP-E-RL**: DQN v4 구현 완료. 단, 현재 고정 K=150 방식이 RL 대비 성능 우위로
> 논문 Table 2 최종 비교에서는 제외(— 표기)됨. 에피소딕 학습 구조로의 개선은 차후 연구 예정.
> `compare_all()`에는 포함되며, 논문 재현 실험은 `compare_paper()` 사용 권장.

---

## 신규 구현 16개 (v5→v7)

| # | 항목 | 파일 |
|---|---|---|
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

## 최종 실험 결과 (Score = LND × PDR 기준, 20회 Monte Carlo)

| 순위 | 프로토콜 | LND (σ) | PDR | Score | 비고 |
|---|---|---|---|---|---|
| **1위** | **AMCP-E** | 69,555 ± 2,915 | 1.679 | **116,783** | 제안 프로토콜 |
| **2위** | **AMCP-E-H2** | ≥ 1,000,000 | 0.102 | **102,400** | 제안 프로토콜 |
| 3위 | GEAR | 12,892 ± 1,030 | 4.990 | 64,332 | |
| 4위 | LEACH | 38,490 ± 2,308 | 1.651 | 63,534 | |
| 4위 | APTEEN | 38,490 ± 2,308 | 1.651 | 63,534 | |
| 5위 | RUMOR | 4,281 ± 262 | 8.200 | 35,104 | |
| 6위 | DEEC | 1,519 ± 572 | 10.636 | 16,155 | |
| 7위 | GAF | 1,322 ± 240 | 9.835 | 13,002 | |
| 8위 | MCP+ | 2,191 ± 18 | 3.946 | 8,646 | |
| 9위 | MCP | 1,093 ± 8 | 3.884 | 4,242 | |
| 10위 | LEACH-C | 875 ± 38 | 4.297 | 3,760 | |
| 11위 | SEP | 67,223 ± 21,507 | 0.042 | 2,823 | ⚠ PDR≈0 (이종 노드 BS 거리 문제) |
| 12위 | EE-LEACH | 27,661 ± 2,518 | 0.097 | 2,664 | |
| 13위 | PEGASIS | 1,519 ± 171 | 0.997 | 1,514 | |
| 14위 | HEED | 615 ± 47 | 2.406 | 1,470 | |
| 15위 | SPIN | 1,361 ± 143 | 0.992 | 1,350 | |
| 最下 | TEEN | 126,486 ± 13,926 | 0.001 | **76** | ⚠ LND 1위이나 PDR≈0 → 편향 지표 |
| — | AMCP-E-RL | — | — | — | 차후 개선 예정 (†주석 참고) |

> ⚠️ **LND 단독 지표 편향 경고**: TEEN·SEP은 LND 상위권이나 데이터 전달률(PDR)이 거의 0에
> 가까워 Score 기준 최하위. 논문에서는 LND×PDR Score를 공정 지표로 채택함.

---

## 커버리지 요약 (41개 개선방안)

| 상태 | 수 | 비율 | 비고 |
|---|---|---|---|
| ✅ 완전 구현 | **29개** | **71%** | 이 중 16개가 v5→v7 신규 |
| ⚠️ 부분 구현 | 1개 | 3% | 이벤트 기반 백오프 (낮은 우선순위) |
| 🔵 시뮬 불필요 | 8개 | 20% | RSSI/TOA/암호화/RBAC/MAC 등 HW 영역 |
| 🟢 차후 연구 | 3개 | 7% | 실제 HW 이식, 대규모 이동성 실험, RL 개선 |

카테고리별:
- RD 계산: 2/4 (2항목 시뮬 불필요)
- 체인 구성: 9/9 (100%)
- 차분전송: 4/4 (100% — 3-mode 완료)
- 슬립/제어: 3/4 (백오프 우선순위 낮음)
- 보안: 1/2 (에너지 추상화 완료, RBAC 불필요)
- 이동성: 5/6 (HW 이식 = 차후 연구)
- 에너지 효율: 4/4 (100%)
- 통계: 4/4 (100%)
- 미래 연구: 4/6 (HW, 백오프 = 차후 연구)

---

## 주요 API

```python
# 기본 실험
from wsn_framework.protocols import get_protocol
proto = get_protocol("AMCP-E")(cfg.protocol, em, cfg.comm)
result = proto.run(topo, 1_000_000, seed=42, run_until_dead=True)
print(f"LND={result.lnd}  PDR={result.pdr:.3f}  Score={result.lnd*result.pdr:,.0f}")

# 19개 전체 비교
from wsn_framework.framework import WSNFramework
fw = WSNFramework.from_yaml("configs/default_scenario.yaml")
results = fw.compare_all(until_all_dead=True)   # 19개 전체
fw.print_summary(results)
fw.export_all(results)

# 논문 Table 2 재현 (AMCP-E-RL 제외, 18개)
results_paper = fw.compare_paper()

# 채널 모델 (log-normal shadowing)
from wsn_framework.core.energy import EnergyConfig, EnergyModel
ec = EnergyConfig(shadowing_std=4.0, shadowing_seed=42)
em = EnergyModel(ec)

# 에너지 하베스팅
ec2 = EnergyConfig(harvesting=True, harvest_rate=0.001, harvest_period=500)

# 모바일 BS (UAV 궤적)
from wsn_framework.core.topology import BaseStation
bs = BaseStation(x=50, y=50, trajectory=[(50,50),(60,40),(70,30)])
bs.move_to(round_num=2)  # → (70, 30)

# AMCP-E 3-mode 차분전송
proto.params.update({
    "diff": True,
    "delta_threshold": 0.1,
    "quantize": True,
    "quant_bits": 2,
})

# PSO 노드 위치 최적화
from wsn_framework.utils.swarm_optimizer import PSOOptimizer
pso = PSOOptimizer(n_nodes=100, n_particles=20, n_iter=50, seed=42)
result = pso.compare_random_vs_pso(n_trials=5)
print(f"개선율: {result['improvement']:.1f}%")
best_positions = pso.optimize()

# 보안 에너지 추상화
from wsn_framework.utils.security_model import SecurityModel, SecurityConfig
sec = SecurityModel(SecurityConfig(enabled=True))
overhead = sec.tx_overhead(4000)   # AES+HMAC 오버헤드 (Joules)

# 병렬 실험 (N=500, 10회 반복)
from wsn_framework.experiment.parallel_experiment import ParallelExperiment
exp = ParallelExperiment("configs/default_scenario.yaml", n_workers=4)
r = exp.run("AMCP-E", n_nodes=500, repetitions=10)
r2 = exp.scalability_test("AMCP-E", node_counts=[100, 200, 500, 1000])

# 통계 검증
from wsn_framework.experiment.metrics import welch_ttest, bootstrap_ci
t, p = welch_ttest(lnd_list_a, lnd_list_b)
lo, hi = bootstrap_ci(lnd_list, n_boot=400, ci=0.95)
```

---

## 에너지 모델 파라미터

```
영역:       100×100 m², N=100, BS=(50,50)m
E0=0.5J,    E_elec=50 nJ/bit
ε_fs=10 pJ/bit/m²,  ε_mp=0.0013 pJ/bit/m⁴
E_agg=5 nJ/bit,     d0 ≈ 87.7m
패킷=4000 bits,     제어=200 bits
shadowing_std=4.0dB (현실적 채널),  harvest_rate=0.0001 J/round
Monte Carlo: 20회, seed 42~61,  run_until_dead=True, max 1,000,000 rounds
```

AMCP-E 최적 파라미터:
```
ch_ratio=0.05, gamma=0.0, reset_k=500
diff=True, e_min_ratio=0.05, delta_threshold=0.0
quantize=False, quant_bits=2
w_dist=0.5, w_energy=0.5
```

---

## 프레임워크 복원 절차 (새 세션에서 재실행 시)

새로운 Claude 또는 Python 환경에서 프레임워크를 복원할 때 아래 4단계를 따르세요.

**Step 1 — zip 해제**
```python
import zipfile
with zipfile.ZipFile('wsn_framework_v7_complete.zip') as z:
    z.extractall('/home/claude/')
print('Restored OK')
```

**Step 2 — 프로토콜 로드 확인 (19개)**
```python
import sys; sys.path.insert(0, '/home/claude')
from wsn_framework.protocols import list_protocols
p = list_protocols()
print(f'{len(p)} protocols: {p}')
# → 19 protocols: ['LEACH', 'LEACH-C', ..., 'GAF']
```

**Step 3 — 단일 실험 빠른 검증**
```python
import sys; sys.path.insert(0, '/home/claude')
from wsn_framework.core.config import ScenarioConfig
from wsn_framework.core.topology import TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.protocols import get_protocol

cfg = ScenarioConfig.from_yaml('/home/claude/wsn_framework/configs/default_scenario.yaml')
cfg.topology.num_nodes = 100
em = EnergyModel(cfg.energy)
t = TopologyManager(cfg.topology, cfg.energy, seed=42)
t.deploy()
r = get_protocol('AMCP-E')(cfg.protocol, em, cfg.comm).run(t, 1000000, 42, 0, run_until_dead=True)
print(f'AMCP-E: LND={r.lnd:,}  PDR={r.pdr:.3f}  Score={r.lnd*r.pdr:,.0f}')
# 기대값: LND≈69,555  PDR≈1.679  Score≈116,783
```

**Step 4 — 참조 수치 (20회 MC, seed 42~61)**

| 프로토콜 | LND | PDR | Score | 순위 |
|---|---|---|---|---|
| AMCP-E | 69,555±2,915 | 1.679 | 116,783 | 1위 |
| AMCP-E-H2 | ≥1,000,000 | 0.102 | 102,400 | 2위 |
| GEAR | 12,892±1,030 | 4.990 | 64,332 | 3위 |
| LEACH | 38,490±2,308 | 1.651 | 63,534 | 4위 |
| TEEN | 126,486±13,926 | 0.001 | 76 | 最下 |

---

## 차후 연구 로드맵

| # | 항목 | 우선순위 | 비고 |
|---|---|---|---|
| 1 | 이벤트 기반 백오프 (Early Backoff) | 낮음 | TEEN 임계값 TX로 대체 가능 |
| 2 | AMCP-E-RL DQN 개선 (에피소딕 학습) | 중간 | State→에너지맵 확장, K 동적화 |
| 3 | 대규모 실험 (N=500~2000, 20회 MC) | 중간 | ParallelExperiment 모듈 활용 |
| 4 | 전체 이동성 실험 (step_mobility 통합) | 낮음 | 속도 1~5 m/round |
| 5 | 실제 HW 이식 (TelosB / NRF52840) | 미래 | C / Contiki-NG 변환 |

---

## 버전 이력

| 태그 | 주요 변경 내용 |
|---|---|
| v5 | shadowing, 하베스팅, 모바일 BS, 3D, MCP 백업 링크, 가중치, 차분전송, TDMA, AMCP-E-H2 구현 |
| v6 | DMCP, AMCP-E-RL DQN v4, 병렬 실험 엔진 추가 |
| v7 | PSO 최적화, IoT-SEC 보안 모델, 3-mode 차분전송 완성, 논문 최종 실험 수행 |

---

## 저자

민복기*, 박지수**, 손진곤*  
\*한국방송통신대학교 대학원 컴퓨터과학과  
\*\*전주대학교 컴퓨터공학과  
contact: minbknim@gmail.com | 2026
