#!/usr/bin/env bash
# =============================================================================
# WSN Framework v8 — GitHub 업로드 자동화 스크립트
# 사용법:
#   chmod +x git_push_v8.sh
#   ./git_push_v8.sh [--dry-run]
#
# 전제:
#   - git clone https://github.com/minbknim/wsn_framework 완료 상태
#   - 스크립트를 wsn_framework/ 루트에서 실행
#   - wsn_v8/ 디렉터리가 wsn_framework/ 와 같은 레벨에 존재
# =============================================================================

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY-RUN] 실제 push 없이 절차만 확인합니다."
fi

run() {
    echo "  $ $*"
    if [[ "$DRY_RUN" == "false" ]]; then
        "$@"
    fi
}

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '.')"
V8_SRC="${REPO_ROOT}/../wsn_v8"

echo ""
echo "========================================================"
echo "  WSN Framework v8 GitHub 업로드 스크립트"
echo "  REPO: $REPO_ROOT"
echo "  V8 소스: $V8_SRC"
echo "========================================================"

# ── 사전 확인 ──────────────────────────────────────────────────────────────
echo ""
echo "[1] 사전 확인"
if [[ ! -d "$REPO_ROOT/.git" ]]; then
    echo "  ❌ git 저장소가 아닙니다: $REPO_ROOT"; exit 1
fi
echo "  ✅ git 저장소 확인"

if [[ ! -d "$V8_SRC" ]]; then
    echo "  ❌ wsn_v8 디렉터리 없음: $V8_SRC"
    echo "     먼저 wsn_framework_v8_complete.zip 을 ../wsn_v8/ 에 압축 해제하세요."
    exit 1
fi
echo "  ✅ wsn_v8 소스 확인"

# ── main 브랜치로 이동 ──────────────────────────────────────────────────────
echo ""
echo "[2] 브랜치 준비"
run git checkout main
run git pull origin main
echo "  ✅ main 브랜치 최신화"

# ── 버전 브랜치 생성 (feature/v8) ──────────────────────────────────────────
echo ""
echo "[3] feature/v8 브랜치 생성"
run git checkout -b feature/v8 2>/dev/null || run git checkout feature/v8
echo "  ✅ feature/v8 브랜치"

# ── v7 수정 파일 반영 ──────────────────────────────────────────────────────
echo ""
echo "[4] v7 수정 파일 복사 (framework.py, README.md, WSN_project_summary.txt, CHANGELOG.md)"

V7_FILES=(
    "framework.py"
    "README.md"
    "WSN_project_summary.txt"
    "CHANGELOG.md"
    "protocols/__init__.py"
)

OUTPUTS="${REPO_ROOT}/../wsn_v8_outputs"  # 이전 대화에서 생성된 outputs 경로
# outputs 경로 자동 탐색
for candidate in \
    "/mnt/user-data/outputs" \
    "${REPO_ROOT}/../outputs" \
    "${HOME}/outputs"
do
    if [[ -f "${candidate}/framework.py" ]]; then
        OUTPUTS="$candidate"; break
    fi
done
echo "  outputs 경로: $OUTPUTS"

copy_if_exists() {
    local src="$1" dst="$2"
    if [[ -f "$src" ]]; then
        mkdir -p "$(dirname "$dst")"
        run cp "$src" "$dst"
        echo "  ✅ 복사: $(basename "$src")"
    else
        echo "  ⚠  없음: $src (건너뜀)"
    fi
}

copy_if_exists "${OUTPUTS}/framework.py"              "${REPO_ROOT}/framework.py"
copy_if_exists "${OUTPUTS}/README_v8.md"              "${REPO_ROOT}/README.md"
copy_if_exists "${OUTPUTS}/WSN_project_summary.txt"   "${REPO_ROOT}/WSN_project_summary.txt"
copy_if_exists "${OUTPUTS}/CHANGELOG_v8.md"           "${REPO_ROOT}/CHANGELOG.md"
copy_if_exists "${OUTPUTS}/protocols__init__.py"      "${REPO_ROOT}/protocols/__init__.py"

# ── v8 신규 파일 복사 ──────────────────────────────────────────────────────
echo ""
echo "[5] v8 신규 파일 복사"

# protocols/
copy_if_exists "${OUTPUTS}/amcp_e_rl_v5.py"         "${REPO_ROOT}/protocols/amcp_e_rl.py"
copy_if_exists "${OUTPUTS}/teen_v2_backoff.py"       "${REPO_ROOT}/protocols/teen.py"

# experiment/
copy_if_exists "${OUTPUTS}/large_scale_experiment.py" "${REPO_ROOT}/experiment/large_scale_experiment.py"
copy_if_exists "${OUTPUTS}/mobility_experiment.py"    "${REPO_ROOT}/experiment/mobility_experiment.py"

# hw_port/
copy_if_exists "${OUTPUTS}/hw_export.py"             "${REPO_ROOT}/hw_port/hw_export.py"

run mkdir -p "${REPO_ROOT}/hw_port/output/telosb"
run mkdir -p "${REPO_ROOT}/hw_port/output/nrf52840"

for fname in amcp_e_params.h energy_model.h amcp_e_core.c amcp_e_core.h contiki_glue.c export_meta.json; do
    copy_if_exists "${V8_SRC}/hw_port/output/telosb/${fname}"   "${REPO_ROOT}/hw_port/output/telosb/${fname}"
    copy_if_exists "${V8_SRC}/hw_port/output/nrf52840/${fname}" "${REPO_ROOT}/hw_port/output/nrf52840/${fname}"
done

# run_v8.py
copy_if_exists "${OUTPUTS}/run_v8.py" "${REPO_ROOT}/run_v8.py"

# .gitignore에 결과 폴더 추가
echo ""
echo "[6] .gitignore 업데이트"
GITIGNORE="${REPO_ROOT}/.gitignore"
IGNORE_ENTRIES=(
    "__pycache__/"
    "*.pyc"
    "*.pyo"
    ".pytest_cache/"
    "results/"
    "*.zip"
    "*.csv"
    "*.png"
    "dist/"
    "build/"
    "*.egg-info/"
    ".DS_Store"
)
touch "$GITIGNORE"
for entry in "${IGNORE_ENTRIES[@]}"; do
    if ! grep -qxF "$entry" "$GITIGNORE" 2>/dev/null; then
        echo "$entry" >> "$GITIGNORE"
        echo "  + $entry"
    fi
done
echo "  ✅ .gitignore 업데이트 완료"

# ── git add & commit ────────────────────────────────────────────────────────
echo ""
echo "[7] git add & commit"
run git add -A

COMMIT_MSG="feat(v8): 차후 계획 5개 전체 구현 완료

[Task 1] AMCP-E-RL DQN v5 — 에피소딕 학습 구조
  - State 3차원 → 14차원 (에너지맵 히스토그램 포함)
  - 동적 K ∈ {3,…,20}, Dueling Double DQN + PER
  - 생애 후반 경험 2× 우선순위, Numpy fallback 지원

[Task 2] TEEN/APTEEN v2 — 이벤트 기반 Early Backoff
  - HT 미달 시 지수 백오프 (×2, 최대 64 라운드)
  - 이벤트 발생 시 즉시 리셋 → 에너지 절약

[Task 3] 대규모 스케일러빌리티 실험 모듈
  - N=100~2000, multiprocessing.Pool 병렬 실행
  - ScalabilityRunner / Analyzer / Reporter
  - CSV·JSON·LaTeX·Matplotlib 출력

[Task 4] 전체 이동성 실험 — step_mobility() 통합
  - MobilityMixin.inject() — 기존 코드 수정 불필요
  - Random Waypoint + 경계 반사
  - MobilityWrapper, MobilityAnalyzer, LND 히트맵

[Task 5] HW 이식 준비 — C/Contiki-NG 코드 자동 생성
  - TelosBProfile, NRF52840Profile (실측 기반)
  - PowerCalibrator — 시뮬↔실측 에너지 보정
  - CCodeGenerator → amcp_e_params.h, energy_model.h,
    amcp_e_core.c/h, contiki_glue.c 자동 생성

[수정] v7 불일치 항목 정정
  - framework.py ALL_PROTOCOLS 11→19개
  - WSN_project_summary.txt 커버리지 수치 논문 기준 정정
  - protocols/__init__.py 19개 레지스트리 완성
  - AMCP-E-RL 논문 미기재 사유 명기
  - README.md 복원 절차·차후 로드맵 추가

refs: WSN_project_summary.txt, wsn_paper_v7_final.docx"

run git commit -m "$COMMIT_MSG"
echo "  ✅ 커밋 완료"

# ── 태그 부착 ───────────────────────────────────────────────────────────────
echo ""
echo "[8] 버전 태그 부착"

# 과거 태그 소급 부착 (해당 커밋이 있는 경우)
# 이미 태그가 있으면 건너뜀
for TAG in v5 v6 v7; do
    if git tag | grep -q "^${TAG}$"; then
        echo "  ⚠  태그 ${TAG} 이미 존재 (건너뜀)"
    else
        # 커밋 메시지에 버전 언급이 있는 커밋 탐색
        COMMIT=$(git log --oneline --grep="${TAG}" --format="%H" | tail -1 || true)
        if [[ -n "$COMMIT" ]]; then
            run git tag "$TAG" "$COMMIT"
            echo "  ✅ 태그 ${TAG} → ${COMMIT:0:8}"
        else
            echo "  ⚠  ${TAG} 커밋 못찾음 — 수동으로 부착 필요"
        fi
    fi
done

# v8 태그
if git tag | grep -q "^v8$"; then
    echo "  ⚠  태그 v8 이미 존재 (건너뜀)"
else
    run git tag -a v8 -m "WSN Framework v8: 차후 계획 5개 전체 구현 완료"
    echo "  ✅ 태그 v8 부착"
fi

# ── push ────────────────────────────────────────────────────────────────────
echo ""
echo "[9] origin에 push"
run git push origin feature/v8 --tags
echo "  ✅ feature/v8 + 태그 push 완료"

# ── main merge 안내 ─────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  ✅ 완료! 다음 단계:"
echo ""
echo "  1. GitHub에서 Pull Request 생성:"
echo "     feature/v8 → main"
echo ""
echo "  2. PR 제목 (권장):"
echo "     feat(v8): 차후 계획 5개 전체 구현 — 에피소딕DQN, EarlyBackoff,"
echo "               대규모실험, 이동성, HW이식"
echo ""
echo "  3. PR 머지 후 main에도 v8 태그 이동:"
echo "     git checkout main && git pull"
echo "     git tag -f v8 HEAD"
echo "     git push origin v8 --force"
echo "========================================================"
