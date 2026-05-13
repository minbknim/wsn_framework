# CHANGELOG — WSN Simulation Framework

모든 주요 변경 사항은 이 파일에 기록됩니다.  
형식: [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)  
버전 관리: [Semantic Versioning](https://semver.org/lang/ko/) (major.minor.patch)

---

## [7.0.0] — 2026-05-12 (태그: `v7`)

### 추가
- `utils/swarm_optimizer.py` — PSO 노드 위치 최적화 (개선율 ~40%)
- `utils/security_model.py` — IoT-SEC 보안 에너지 추상화 (AES+HMAC 오버헤드)
- `protocols/amcp_e.py` — 3-mode 차분전송 완성 (quantize 모드 추가)
- 논문 최종 실험 수행 (20회 MC, seed 42~61, 19개 프로토콜, Score=LND×PDR)

### 변경
- `framework.py` — ALL_PROTOCOLS 11→19개 업데이트 (논문 v7 기준)
  - 신규 추가: AMCP-E, AMCP-E-H2, AMCP-E-RL, DMCP, SPIN, RUMOR, GEAR, GAF
  - `compare_all()` docstring 수정 (19개 명시)
  - `compare_paper()` 신규 메서드 추가 (논문 Table 2 재현, AMCP-E-RL 제외)
  - `print_summary()` — Score=LND×PDR 기준 순위 표시 추가
- `README.md` — 커버리지 수치 논문 정본 확인(29개/71%), 복원 절차 추가,
  AMCP-E-RL 주석 추가, 버전 이력 표 추가, 전체 실험 결과 18→16위 표 확장

### 수정
- `WSN_project_summary.txt` — 커버리지 수치 논문 기준으로 정정
  - 완전구현: 32개(78%) → **29개(71%)**
  - 시뮬불필요: 6개(15%) → **8개(20%)**
  - 차후연구: 2개(5%) → **3개(7%)**
  - AMCP-E-RL 실험 미기재 사유 명기 (†)

### 실험 결과 (최종)
| 순위 | 프로토콜 | LND | PDR | Score |
|---|---|---|---|---|
| 1 | AMCP-E | 69,555±2,915 | 1.679 | **116,783** |
| 2 | AMCP-E-H2 | ≥1,000,000 | 0.102 | 102,400 |
| 3 | GEAR | 12,892±1,030 | 4.990 | 64,332 |
| … | … | … | … | … |
| 最下 | TEEN | 126,486±13,926 | 0.001 | 76 |

---

## [6.0.0] — 2026-04 (태그: `v6`)

### 추가
- `protocols/dmcp.py` — DMCP (분산형 그리디 체인, 제안 프로토콜)
- `protocols/amcp_e_rl.py` — AMCP-E-RL DQN v4 강화학습 프로토콜
- `experiment/parallel_experiment.py` — 병렬 실험 엔진 (N=2000 지원)

### 변경
- `protocols/amcp_e_rl.py` — DQN State 공간 개선, replay buffer 최적화

---

## [5.0.0] — 2026-03 (태그: `v5`)

### 추가
- `core/energy.py` — log-normal shadowing 채널 모델 (shadowing_std 파라미터)
- `core/energy.py` — 에너지 하베스팅 (태양광 sin² 모델)
- `core/topology.py` — 모바일 BS (UAV 궤적 지원)
- `core/topology.py` — 3D 좌표·거리 계산
- `protocols/mcp.py` — MCP 예비 링크/백업 경로
- `protocols/mcp.py` — 체인 길이 균등 분배
- `protocols/mcp.py`, `amcp_e.py` — 적응형 가중치 w_dist/w_energy
- `protocols/amcp_e.py` — 임계값 기반 하이브리드 차분전송 (delta_threshold)
- `protocols/base.py` — TDMA 슬롯 스케줄링
- `protocols/amcp_e_h2.py` — AMCP-E-H2 (2-tier 하이브리드, 제안 프로토콜)

### 변경
- `protocols/teen.py` — HT=50°C, ST=5°C (기존 HT=0.1 수정)
- `protocols/sep.py` — m_frac=0.10, alpha=0.5 (기존 동질 노드 설정 수정)

---

## [초기 버전] — 2026-02 이전 (태그: `v1`~`v4`, 미공개)

### 포함 프로토콜 (11개)
LEACH, LEACH-C, HEED, PEGASIS, TEEN, APTEEN, SEP, DEEC, EE-LEACH, MCP, MCP+

### 기본 기능
- First-order Radio Model 에너지 모델
- ScenarioConfig YAML 로더
- ExperimentManager (Monte Carlo)
- ResultExporter (CSV/JSON)
- Plotter (alive_nodes 그래프)

---

## 차후 계획 (미출시)

### [7.1.0] — 예정
- AMCP-E-RL 에피소딕 학습 구조 개선 (State → 에너지맵)
- 이벤트 기반 백오프 구현 (`protocols/teen.py`)

### [8.0.0] — 예정
- N=500~2000 대규모 전체 실험 (20회 MC)
- 전체 이동성 실험 (`topology.step_mobility()` 통합)
- 실제 HW 이식 (TelosB / NRF52840, C / Contiki-NG)
