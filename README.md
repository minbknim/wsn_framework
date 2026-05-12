# WSN Simulation Framework

NS-3 + Python 통합 WSN 시뮬레이션 프레임워크  
11개 라우팅 프로토콜 비교 실험 패키지

---

## 📁 패키지 구성

```
wsn_framework.zip          ← 프레임워크 소스 코드
wsn_results_data.zip       ← 실험 결과 (summary + 그래프, 891KB)
wsn_results_full.zip       ← 실험 결과 전체 (토폴로지 프레임 1,042장, 50MB)
wsn_final_paper.docx       ← KIPS 양식 완성 논문
```

---

## 🔬 지원 프로토콜 (11개)

| 파일 | 프로토콜 | 논문 |
|------|---------|------|
| leach.py | LEACH | Heinzelman et al., HICSS 2000 |
| leach_c.py | LEACH-C | Heinzelman et al., IEEE TWC 2002 |
| heed.py | HEED | Younis & Fahmy, IEEE TMC 2004 |
| pegasis.py | PEGASIS | Lindsey & Raghavendra, IEEE Aerospace 2002 |
| teen.py | TEEN | Manjeshwar & Agrawal, IPDPS 2001 |
| apteen.py | APTEEN | Manjeshwar & Agrawal, IPDPS 2002 |
| sep.py | SEP | Smaragdakis et al., SANPA 2004 |
| deec.py | DEEC | Qing et al., Computer Comm. 2006 |
| ee_leach.py | EE-LEACH | 멀티홉 CH 릴레이 변형 |
| mcp.py | MCP / MCP+ | Min et al., KIPS 2019 |

---

## 🚀 빠른 시작

```python
import sys
sys.path.insert(0, ".")  # wsn_framework 상위 폴더

from wsn_framework.core.config import ScenarioConfig
from wsn_framework.experiment.manager import ExperimentManager
from wsn_framework.protocols import list_protocols

# 설정 로드
cfg = ScenarioConfig.from_yaml("wsn_framework/configs/default_scenario.yaml")
cfg.simulation.repetitions = 20
cfg.topology.num_nodes = 100

# 실험 관리자 생성 (결과 폴더: results/YYYYMMDD_HHMMSS/)
mgr = ExperimentManager(cfg, output_dir="results")

# 11개 프로토콜 전체 비교 (run_until_dead=모든 노드 사망까지)
comparison = mgr.compare(
    list_protocols(),
    repetitions=20,
    run_until_dead=True,           # LND 정밀 측정
    save_topo_changes=True,        # 토폴로지 변화 저장
    topo_save_interval=500,        # 500라운드마다 스냅샷
)

# 결과 출력
for proto, agg in comparison.items():
    print(f"{proto}: FND={agg.fnd_mean:.0f}  LND={agg.lnd_mean:.0f}")
```

---

## 📊 실험 결과 요약 (N=100, 20회 run_until_dead)

| Protocol | FND | HND | LND | PDR(%) |
|----------|-----|-----|-----|--------|
| SEP | 191.6 | 393.6 | **278,493** | 0.01 |
| LEACH | 185.5 | 8,628 | **37,741** | 1.51 |
| TEEN | 194.7 | 8,635 | **37,726** | 1.51 |
| APTEEN | 189.4 | 8,633 | **37,735** | 1.51 |
| EE-LEACH | **8,177** | 18,652 | 28,383 | 0.09 |
| MCP+ | 327.1 | 2,030 | 2,180 | 3.94 |
| PEGASIS | 215.9 | 1,131 | 1,519 | 1.00 |
| MCP | 163.8 | 1,019 | 1,093 | 3.88 |
| DEEC | 264.2 | 411 | 785 | **9.17** |
| LEACH-C | **364.8** | 392 | 408 | 4.81 |
| HEED | 152.1 | 301.7 | 362 | 2.27 |

---

## 📂 결과 폴더 구조

```
wsn_results_20260408_082941/
├── LEACH/
│   ├── topology_initial_seed42.png   ← 초기 노드 배치도
│   ├── topology_frames/              ← 라운드별 변화 (104장)
│   │   ├── round_000152_alive99_dead1.png
│   │   └── round_036379_alive0_dead100.png
│   └── summary.txt
├── PEGASIS/ MCP/ MCP+/ SEP/ ...  (11개 프로토콜)
├── comparison_summary.csv
└── figures/
    ├── dashboard.png
    ├── lnd_comparison.png
    ├── lifetime_bars.png
    ├── pdr_comparison.png
    └── energy_balance.png
```

---

## 의존성

```
pip install numpy pandas matplotlib seaborn scipy networkx pyyaml
```

---

## 신규 프로토콜 등록 방법

```python
from wsn_framework.protocols.base import BaseProtocol
from wsn_framework.protocols import register

class MyProtocol(BaseProtocol):
    name = "MY-PROTO"
    default_params = {"ch_ratio": 0.05}

    def select_cluster_heads(self, alive_nodes, round_num, bs):
        # CH 선출 로직
        ...
        return ch_ids, cluster_map

    def run_round(self, alive_nodes, ch_ids, cluster_map, bs, round_num):
        # 에너지 소모 계산
        ...
        return packets_to_bs

register(MyProtocol)
```
