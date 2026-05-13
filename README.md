# WSN 시뮬레이션 프레임워크 v5 (최종판)

## 개요
NS-3·Python 통합 WSN 시뮬레이션 프레임워크.  
17개 프로토콜(16개 기존 + AMCP-E-RL) 구현, 5가지 구조적 문제점 수정 완료.

## 등록 프로토콜 (17개)

| 분류 | 프로토콜 |
|------|---------|
| 계층형 (6) | LEACH, LEACH-C, HEED, TEEN★, APTEEN, SEP★ |
| 이종계층 (1) | DEEC |
| 체인형 (1) | PEGASIS |
| 멀티홉 (1) | EE-LEACH |
| 멀티체인 (3) | MCP, MCP+, **AMCP-E** (제안), AMCP-E-RL |
| 데이터중심 (2) | SPIN, RUMOR★ |
| 위치기반 (2) | GEAR★, GAF★ |

★=최종판에서 개선  
**굵게** = 제안 프로토콜

## 주요 개선사항 (v1→v5, 10개)

1. **PDR 재정의**: `packets/max(LND,1)` — 라운드당 평균 BS 도달 패킷 수
2. **슬립 에너지**: `model_idle=True` 선택적 반영 (base.py)
3. **제어패킷 에너지**: `_dissipate_ctrl()`, `_recv_ctrl()` (base.py)
4. **TEEN 임계값**: HT=50°C, ST=5°C + sensing 시뮬레이션 → LND +3.35×
5. **SEP 이종 노드**: m_frac=10%, alpha=0.5 → σ 81%↓
6. **GEAR 자동 검증**: `_validate_params()` — tx_range 자동 안전 조정
7. **RUMOR 경로테이블**: `_best_next_hop()` — 경로+Greedy 가중결합
8. **RandomWaypoint 이동성**: `MobilityModel` 클래스 (topology.py)
9. **GAF 이동성 지원**: `mobile=True` 격자 동적 재배정
10. **t-검정 자동화**: `pairwise_ttest()`, `bootstrap_ci()` (metrics.py)

## 설치 및 실행

```bash
pip install -r requirements.txt

# 단일 프로토콜 실험
python -m wsn_framework run --protocol AMCP-E --repetitions 20 --run-until-dead

# 16개 비교
python -m wsn_framework compare --protocols all --repetitions 20

# 이동성 활성화 (GAF)
python -m wsn_framework run --protocol GAF --mobile True
```

## 최종 실험 결과 (20회 Monte Carlo, run_until_dead)

| 프로토콜 | FND | LND±σ | PDR |
|---------|-----|--------|-----|
| **AMCP-E** ◀ | **7,598±445** | **69,555±2,915** | **1.679** |
| TEEN ★ | 5,878±1,962 | 126,486±13,926 | 0.001 |
| SEP ★ | 426±25 | 106,487±46,219 | 0.000 |
| EE-LEACH | 7,575±1,846 | 27,661±2,518 | 0.095 |
| GEAR ‡ | 8,007±166 | 12,892±1,030 | 4.990 |
| LEACH | 3,850±309 | 38,406±1,709 | 1.651 |
| DEEC | 612±35 | 1,447±439 | 10.822 |
| GAF ‡ | 524±103 | 1,296±186 | 9.835 |

## 에너지 모델 파라미터

```
배포 영역: 100×100 m², BS=(50,50)m, N=100
E��=0.5J, E_elec=50nJ/bit, ε_fs=10pJ/bit/m²
ε_mp=0.0013pJ/bit/m⁴, E_agg=5nJ/bit
패킷=4000bits, 제어=200bits
```

## 통계 검증 API

```python
from wsn_framework.experiment.metrics import pairwise_ttest, bootstrap_ci

# Welch t-검정
results = pairwise_ttest(experiment_results, metric="lnd", alpha=0.05)

# Bootstrap 95%CI
lo, hi = bootstrap_ci(lnd_values, n_boot=1000, ci=0.95)
```

## 이동성 모델 사용

```python
from wsn_framework.core.topology import TopologyManager, MobilityModel

mob  = MobilityModel(area_size=100, speed_max=2.0, pause_rounds=10)
topo = TopologyManager(cfg.topology, cfg.energy, seed=42, mobility=mob)
topo.deploy()

# 매 라운드 이동
topo.step_mobility()
```

## 저자
민복기, 박지수, 손진곤  
한국방송통신대학교 / 전주대학교 | 2026
