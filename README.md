# WSN Framework

**NS3 + Python 통합 무선 센서 네트워크 시뮬레이션 프레임워크**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![NS3](https://img.shields.io/badge/NS--3-3.40-green)](https://nsnam.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 개요

WSN Framework는 무선 센서 네트워크(Wireless Sensor Network) 라우팅 프로토콜 연구를 위한 **재현 가능하고 확장 가능한** 시뮬레이션 환경을 제공합니다.

**핵심 설계 목표:**
- **동일 환경 보장**: 비교 대상 프로토콜 전체가 동일한 노드 배치·에너지·통신 조건에서 실행됨
- **NS3 연동**: Docker 컨테이너 내 NS-3.40 바이너리와 Python을 Jinja2 스크립트 생성 방식으로 연결
- **플러그인 확장**: `BaseProtocol` 상속 한 번으로 새 프로토콜 등록 가능
- **자동 분석**: Monte Carlo 반복 실험 → 통계 검정(Welch t-test) → CSV/JSON/LaTeX/그래프 자동 생성

---

## 목차

1. [아키텍처](#아키텍처)
2. [빠른 시작](#빠른-시작)
3. [설치](#설치)
4. [설정 파일](#설정-파일)
5. [CLI 사용법](#cli-사용법)
6. [Python API](#python-api)
7. [내장 프로토콜](#내장-프로토콜)
8. [커스텀 프로토콜 추가](#커스텀-프로토콜-추가)
9. [결과 산출물](#결과-산출물)
10. [프로젝트 구조](#프로젝트-구조)
11. [테스트](#테스트)
12. [Docker 환경](#docker-환경)
13. [파라미터 레퍼런스](#파라미터-레퍼런스)

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│              Python Interface Layer                      │
│         CLI (Click) │ YAML Parser │ WSNFramework API    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  Framework Core                          │
│    ScenarioConfig │ ExperimentManager │ ProtocolRegistry │
└──────┬────────────┬──────────┬────────────┬─────────────┘
       │            │          │            │
┌──────▼──┐  ┌──────▼──┐ ┌────▼────┐ ┌────▼──────┐
│Topology │  │ Energy  │ │Protocol │ │ NS3Bridge │
│Manager  │  │  Model  │ │Plugins  │ │(Jinja2+CC)│
└──────┬──┘  └──────┬──┘ └────┬────┘ └────┬──────┘
       └────────────┴──────────┴──────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                 Simulation Engine                        │
│      Round Scheduler │ Monte Carlo │ Event Collector     │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   Output Layer                           │
│   MetricsCollector │ ResultExporter │ Plotter           │
│   CSV │ JSON │ LaTeX │ 7종 Matplotlib 그래프            │
└─────────────────────────────────────────────────────────┘
```

### 핵심 설계 원칙

**동일 환경 보장 메커니즘**

`ScenarioConfig.clone_for_protocol()`은 YAML에 정의된 토폴로지·에너지·통신 파라미터를 그대로 유지한 채 프로토콜 이름만 교체한 복사본을 생성합니다. `ExperimentManager.compare()`는 동일한 시드 시퀀스(`seed`, `seed+1`, ..., `seed+N-1`)를 모든 프로토콜에 동일하게 적용합니다.

```python
# 내부 동작 방식
for proto in protocols:
    for rep in range(repetitions):
        seed = base_seed + rep          # 모든 프로토콜이 동일 seed 사용
        topo = TopologyManager(seed=seed).deploy()   # 동일 노드 위치
        result = run_protocol(proto, topo)
```

---

## 빠른 시작

### Docker (권장 — NS3 설치 불필요)

```bash
git clone https://github.com/yourorg/wsn_framework.git
cd wsn_framework

# 1. 이미지 빌드 (최초 1회, 약 20-30분)
bash scripts/docker_run.sh build

# 2. 4개 프로토콜 비교 실험 실행 (결과는 ./results/ 에 저장)
bash scripts/docker_run.sh compare \
    configs/default_scenario.yaml \
    LEACH,HEED,PEGASIS,SEP \
    100

# 3. 대화형 쉘 진입
bash scripts/docker_run.sh shell
```

### Python 직접 (NS3 없는 환경, Python 에너지 모델 사용)

```bash
pip install -e .

# 비교 실험
wsn compare \
    --config  configs/default_scenario.yaml \
    --protocols LEACH,HEED,PEGASIS,SEP,TEEN \
    --reps    100 \
    --output  results/

# 토폴로지 그림만 생성
wsn topology --config configs/default_scenario.yaml --output results/figures/topo.png
```

---

## 설치

### 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.9+ |
| NS-3 (선택) | 3.40 |
| Docker (선택) | 20.0+ |

### Python 패키지 설치

```bash
pip install -e .
# 또는
pip install -r requirements.txt
```

**의존 패키지**: numpy, pandas, matplotlib, scipy, jinja2, pyyaml, click, networkx, seaborn, tabulate

---

## 설정 파일

모든 실험 파라미터는 YAML 한 파일로 관리됩니다.

```yaml
# configs/default_scenario.yaml

topology:
  area_width:   100.0        # 시뮬레이션 영역 가로 (m)
  area_height:  100.0        # 시뮬레이션 영역 세로 (m)
  num_nodes:    100          # 센서 노드 수
  deployment:   "random"     # random | grid | uniform
  bs_position:  [50.0, 50.0] # Base Station 위치 (x, y)
  mobility:     "static"     # static | mobile

energy:
  initial_energy: 0.5        # 초기 에너지 (J)
  e_elec:   50.0e-9          # 회로 에너지 50 nJ/bit
  e_amp_fs: 100.0e-12        # Free-space 100 pJ/bit/m²
  e_amp_mp: 0.0013e-12       # Multipath 0.0013 pJ/bit/m⁴
  e_agg:    5.0e-9           # 데이터 집계 5 nJ/bit
  heterogeneous: false       # true 시 het_* 파라미터 적용

comm:
  tx_range:         100.0    # 최대 전송 거리 (m)
  packet_size:      4000     # 데이터 패킷 (bits)
  ctrl_packet_size: 200      # 제어 패킷 (bits)
  channel_model:    "first_order"

protocol:
  name:     "LEACH"
  ch_ratio: 0.05             # Cluster Head 비율
  routing:  "single_hop"

simulation:
  rounds:      2000          # 총 라운드 수
  repetitions: 100           # Monte Carlo 반복 횟수
  seed:        42            # 기준 랜덤 시드
  parallel:    true
  n_jobs:      -1            # -1 = 모든 CPU 코어
```

> **주의**: `protocol.name`은 단일 프로토콜 실행 시에만 사용됩니다.  
> `wsn compare` 명령은 이 설정을 공통 기반으로 각 프로토콜에 동일하게 적용합니다.

---

## CLI 사용법

```bash
# 전체 도움말
wsn --help

# 단일 프로토콜 Monte Carlo 실험
wsn run \
    --config   configs/default_scenario.yaml \
    --protocol LEACH \
    --reps     100 \
    --output   results/leach/

# 다중 프로토콜 비교 (핵심 기능)
wsn compare \
    --config    configs/default_scenario.yaml \
    --protocols LEACH,HEED,PEGASIS,SEP,TEEN \
    --reps      100 \
    --output    results/comparison/

# 파라미터 스윕 (노드 수 변화에 따른 성능)
wsn sweep \
    --config    configs/default_scenario.yaml \
    --protocols LEACH,HEED,SEP \
    --param     topology.num_nodes \
    --values    50,100,200,500 \
    --output    results/sweep_nodes/

# 초기 토폴로지 시각화만 생성
wsn topology \
    --config configs/default_scenario.yaml \
    --output results/figures/initial_topology.png

# 등록된 프로토콜 목록
wsn list-protocols
```

---

## Python API

### 기본 사용법

```python
from wsn_framework import WSNFramework

# YAML에서 로드
fw = WSNFramework.from_yaml(
    "configs/default_scenario.yaml",
    output_dir="results/"
)

# 단일 프로토콜 실험
agg = fw.run("LEACH", repetitions=100)
print(f"FND: {agg.fnd_mean:.1f} ± {agg.fnd_std:.1f}")

# 다중 프로토콜 비교
results = fw.compare(
    ["LEACH", "HEED", "PEGASIS", "SEP", "TEEN"],
    repetitions=100
)

# 요약 테이블 출력
fw.print_summary(results)

# 전체 산출물 자동 생성 (CSV + JSON + LaTeX + 7종 그래프)
fw.export_all(results)

# 토폴로지 그림 저장
fw.save_topology(output_path="results/figures/topology.png")
```

### 파라미터 스윕

```python
# 노드 수에 따른 프로토콜 성능 비교
sweep_results = fw.sweep(
    protocols=["LEACH", "HEED", "SEP"],
    param="topology.num_nodes",
    values=[50, 100, 200, 500]
)
# 결과: {"50": {LEACH: agg, HEED: agg, ...}, "100": {...}, ...}
```

### 저수준 API

```python
from wsn_framework.core.config import ScenarioConfig
from wsn_framework.core.topology import TopologyManager
from wsn_framework.core.energy import EnergyModel
from wsn_framework.protocols.builtin import get_protocol
from wsn_framework.experiment.manager import ExperimentManager
from wsn_framework.experiment.metrics import Comparator
from wsn_framework.output.plotter import Plotter

# 설정 직접 생성
cfg = ScenarioConfig.from_yaml("configs/default_scenario.yaml")
cfg.validate()

# 토폴로지 시각화 (시뮬레이션 없이)
topo = TopologyManager(cfg.topology, cfg.energy, seed=42)
topo.deploy()
topo.visualize("figures/topology.png", tx_range=100.0)

# 비교 실험
mgr  = ExperimentManager(cfg, output_dir="results/")
comp = mgr.compare(["LEACH", "HEED"], repetitions=50)

# 통계 비교
c    = Comparator(comp)
df   = c.summary_dataframe()
pval = c.pairwise_ttest("fnd")   # Welch t-test p-value 행렬
rank = c.rank("fnd_mean")

# 그래프
Plotter("results/").plot_dashboard(comp)
```

---

## 내장 프로토콜

| 프로토콜 | 전체 이름 | 주요 특징 | 참고 |
|---|---|---|---|
| `LEACH` | Low-Energy Adaptive Clustering Hierarchy | 확률적 CH 선출, epoch 기반 | Heinzelman et al., 2000 |
| `HEED` | Hybrid Energy-Efficient Distributed Clustering | 잔여 에너지 비례 CH 확률 | Younis & Fahmy, 2004 |
| `PEGASIS` | Power-Efficient GAthering in Sensor Information Systems | 체인 기반 token-passing | Lindsey & Raghavendra, 2002 |
| `SEP` | Stable Election Protocol | 이종 노드 에너지 가중 선출 | Smaragdakis et al., 2004 |
| `TEEN` | Threshold-sensitive Energy Efficient Network | 하드/소프트 임계값 기반 전송 | Manjeshwar & Agrawal, 2001 |

---

## 커스텀 프로토콜 추가

`BaseProtocol`을 상속하고 두 메서드만 구현하면 됩니다.

```python
from wsn_framework.protocols.base import BaseProtocol
from wsn_framework.protocols.builtin import register
from typing import List, Dict, Tuple

class MyProtocol(BaseProtocol):
    name = "MYPROTO"
    default_params = {"threshold": 0.1}

    def select_cluster_heads(
        self, alive_nodes, round_num, bs
    ) -> Tuple[List[int], Dict[int, int]]:
        """CH 선출 로직. (ch_id_list, {node_id: ch_id}) 반환."""
        # 에너지가 평균 이상인 노드를 CH로 선출
        avg_e = sum(n.energy for n in alive_nodes) / len(alive_nodes)
        ch_ids = [n.node_id for n in alive_nodes if n.energy >= avg_e]
        cluster_map = self._assign_members_to_nearest_ch(alive_nodes, ch_ids)
        return ch_ids, cluster_map

    def run_round(
        self, alive_nodes, ch_ids, cluster_map, bs, round_num
    ) -> int:
        """1 라운드 에너지 소모 처리. BS 수신 패킷 수 반환."""
        node_map = {n.node_id: n for n in alive_nodes}
        pkts = 0
        for node in alive_nodes:
            ch_id = cluster_map.get(node.node_id)
            if ch_id and ch_id != node.node_id:
                self._dissipate_member(node, node_map[ch_id])
        for ch_id in ch_ids:
            ch = node_map.get(ch_id)
            if ch and ch.alive:
                members = [node_map[nid] for nid, cid in cluster_map.items()
                           if cid == ch_id and nid != ch_id and nid in node_map]
                self._dissipate_ch(ch, members, bs)
                pkts += 1
        return pkts

# 등록 (이후 wsn compare -p MYPROTO 로 사용 가능)
register(MyProtocol)
```

---

## 결과 산출물

`fw.export_all(results)` 실행 시 아래 파일이 `output_dir/`에 생성됩니다.

### 데이터 파일

| 파일 | 내용 |
|------|------|
| `summary.csv` | 프로토콜별 평균/표준편차 요약 |
| `summary.json` | 동일 내용 JSON 형식 |
| `results_table.tex` | LaTeX `\begin{table}` 형식 |
| `per_round_alive.csv` | 라운드별 생존 노드 수 (전 프로토콜) |
| `per_round_energy.csv` | 라운드별 잔여 에너지 합계 |
| `per_round_packets.csv` | 라운드별 BS 수신 패킷 수 |
| `ttest_fnd.csv` | FND 기준 Welch t-test p-value 행렬 |
| `ttest_hnd.csv` | HND 기준 동일 |

### 그래프 파일 (`figures/`)

| 파일 | 내용 |
|------|------|
| `topology_<PROTO>_seed<N>.png` | 프로토콜별 초기 노드 배치 (에너지 컬러맵) |
| `topology_shared_seed<N>.png` | 공유 토폴로지 오버뷰 |
| `alive_nodes.png` | 라운드별 생존 노드 수 (평균 ± 표준편차) |
| `energy_consumption.png` | 라운드별 잔여 에너지 추이 |
| `lifetime_bars.png` | FND / HND / LND 막대 그래프 |
| `pdr_comparison.png` | PDR 비교 막대 그래프 |
| `energy_balance.png` | 에너지 균형도 분산 비교 |
| `ttest_heatmap.png` | Welch t-test p-value 히트맵 |
| `dashboard.png` | 6개 지표 종합 대시보드 |

### 주요 성능 지표 정의

| 지표 | 정의 |
|------|------|
| FND | First Node Dead — 첫 번째 노드가 사망한 라운드 |
| HND | Half Node Dead — 절반 노드가 사망한 라운드 |
| LND | Last Node Dead — 마지막 노드가 사망한 라운드 |
| PDR | Packet Delivery Ratio — BS 수신 패킷 / 총 전송 시도 패킷 |
| E-balance | 최종 잔여 에너지 분산 (낮을수록 균등 소모) |
| Avg CH | 라운드당 평균 클러스터 헤드 수 |

---

## 프로젝트 구조

```
wsn_framework/
├── __init__.py                    # 패키지 진입점
├── framework.py                   # WSNFramework (최상위 API)
├── cli.py                         # Click CLI (wsn 명령어)
├── setup.py                       # 패키지 설치 설정
├── requirements.txt               # Python 의존성
│
├── core/                          # 핵심 데이터 모델
│   ├── config.py                  # ScenarioConfig + 서브 dataclass
│   ├── topology.py                # TopologyManager, SensorNode, 시각화
│   ├── energy.py                  # First-order 라디오 에너지 모델
│   └── result.py                  # ExperimentResult, AggregatedResult
│
├── protocols/                     # 프로토콜 플러그인
│   ├── base.py                    # BaseProtocol (ABC)
│   └── builtin.py                 # LEACH, HEED, PEGASIS, SEP, TEEN
│
├── ns3/                           # NS3 연동
│   ├── bridge.py                  # NS3Bridge (native/python 모드 자동 선택)
│   └── templates/wsn_base.cc.j2  # Jinja2 C++ 템플릿
│
├── experiment/                    # 실험 실행 및 집계
│   ├── manager.py                 # ExperimentManager (Monte Carlo)
│   └── metrics.py                 # MetricsCollector, Comparator
│
├── output/                        # 결과 출력
│   ├── exporter.py                # CSV / JSON / LaTeX 익스포터
│   └── plotter.py                 # Matplotlib 7종 그래프
│
├── configs/                       # 시나리오 설정 파일
│   ├── default_scenario.yaml      # 표준 100노드 동질 환경
│   └── heterogeneous_scenario.yaml # 이종 노드 환경 (SEP 최적화)
│
├── tests/
│   └── test_framework.py          # 31개 단위/통합 테스트
│
├── scripts/
│   ├── run_compare.sh             # 컨테이너 내 비교 실험 스크립트
│   └── docker_run.sh              # 호스트에서 Docker 실행 도우미
│
└── docker/
    ├── Dockerfile                 # Ubuntu 22.04 + NS3-3.40 + Python
    └── docker-compose.yml         # 볼륨 마운트 설정
```

---

## 테스트

```bash
# pytest 사용 (Docker 환경)
pytest tests/test_framework.py -v

# pytest 없는 환경
PYTHONPATH=. python3 tests/test_framework.py
```

### 테스트 커버리지 (31개)

| 범주 | 테스트 수 | 주요 내용 |
|------|-----------|-----------|
| Config | 3 | 검증, clone, YAML 직렬화 |
| Topology | 4 | 배포, 재현성, 시드 차이, 그림 생성 |
| Energy Model | 4 | free-space/multipath 수식, Rx, d₀ |
| Protocols | 8 | 5종 실행, 재현성, 에너지 단조 감소 |
| ExperimentManager | 3 | 단일 실행, Monte Carlo, 비교 |
| Comparator | 3 | summary DF, t-test 대각선, 순위 |
| Exporter | 1 | 6개 파일 생성 |
| Plotter | 1 | 7개 그래프 생성 |
| WSNFramework API | 3 | compare+export, 토폴로지, YAML 로드 |

---

## Docker 환경

### 이미지 구성

```
Base: Ubuntu 22.04 LTS
├── Build tools: gcc, cmake, ninja-build
├── NS-3.40 (소스 빌드, Python 바인딩 활성화)
├── Python 3.11 + pip 패키지
└── wsn_framework (pip install -e)
```

### docker-compose 서비스

```yaml
# 실험 실행
docker-compose -f docker/docker-compose.yml run wsn compare \
    --config /workspace/configs/default_scenario.yaml \
    --protocols LEACH,HEED,SEP \
    --reps 100

# 대화형 셸
docker-compose -f docker/docker-compose.yml run wsn-shell
```

### 볼륨 마운트

| 호스트 | 컨테이너 | 용도 |
|--------|----------|------|
| `./results/` | `/workspace/results/` | 결과 파일 영구 저장 |
| `./configs/` | `/workspace/configs/` | 사용자 설정 파일 공유 |

### NS3 동작 모드

| 모드 | 조건 | 동작 |
|------|------|------|
| `native` | `$NS3_PATH` 설정 + ns3 바이너리 존재 | Jinja2→C++ 스크립트 생성 → ns3 실행 → trace 파싱 |
| `python` | NS3 없음 (기본) | Python First-order 에너지 모델로 완전 시뮬레이션 |

---

## 파라미터 레퍼런스

### 에너지 모델 (First-order Radio Model)

```
ETx(k, d) = k·E_elec + k·ε_amp·d^n

  n=2 (Free Space,  d < d₀): ε_amp = ε_fs  = 100 pJ/bit/m²
  n=4 (Multipath,   d ≥ d₀): ε_amp = ε_mp  = 0.0013 pJ/bit/m⁴

ERx(k)    = k·E_elec                     E_elec = 50 nJ/bit
EDA(k)    = k·E_agg                      E_agg  = 5 nJ/bit/signal

d₀ = √(ε_fs / ε_mp) ≈ 277.4 m  (기본 설정 기준)
```

### 표준 비교 환경 (WSN 논문 관행)

| 파라미터 | 기본값 | 단위 |
|----------|--------|------|
| 영역 크기 | 100 × 100 | m² |
| 노드 수 | 100 | 개 |
| 초기 에너지 | 0.5 | J |
| BS 위치 | (50, 50) | m |
| CH 비율 p | 0.05 | - |
| 패킷 크기 | 4,000 | bits |
| 라운드 수 | 2,000 | - |
| 반복 횟수 | 100 | 회 |
| 난수 시드 | 42 | - |

---

## 참고 문헌

1. Heinzelman, W. R., Chandrakasan, A., & Balakrishnan, H. (2000). Energy-efficient communication protocol for wireless microsensor networks. *HICSS-33*.
2. Younis, O., & Fahmy, S. (2004). HEED: A hybrid, energy-efficient, distributed clustering approach for ad hoc sensor networks. *IEEE TMC, 3*(4), 366–379.
3. Lindsey, S., & Raghavendra, C. S. (2002). PEGASIS: Power-efficient gathering in sensor information systems. *IEEE Aerospace Conference*.
4. Smaragdakis, G., Matta, I., & Bestavros, A. (2004). SEP: A stable election protocol for clustered heterogeneous wireless sensor networks. *SANPA*.
5. Manjeshwar, A., & Agrawal, D. P. (2001). TEEN: A routing protocol for enhanced efficiency in wireless sensor networks. *IPDPS*.

---

## 라이선스

MIT License — 자세한 내용은 [LICENSE](LICENSE) 참조
