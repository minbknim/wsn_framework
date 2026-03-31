#!/usr/bin/env bash
# scripts/docker_run.sh — Docker 이미지 빌드 및 실행 도우미
set -euo pipefail

CMD="${1:-compare}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

IMAGE="wsn-framework:latest"
RESULTS_DIR="$PROJECT_DIR/results"
CONFIGS_DIR="$PROJECT_DIR/configs"

mkdir -p "$RESULTS_DIR" "$CONFIGS_DIR"

# ── Build ─────────────────────────────────────────────────────────────────────
if [[ "$CMD" == "build" ]]; then
    echo "[1/1] Docker 이미지 빌드 중 …"
    docker build -f "$PROJECT_DIR/docker/Dockerfile" \
                 -t "$IMAGE" "$PROJECT_DIR"
    echo "✓  빌드 완료: $IMAGE"
    exit 0
fi

# ── Compare ───────────────────────────────────────────────────────────────────
if [[ "$CMD" == "compare" ]]; then
    CONFIG="${2:-/workspace/configs/default_scenario.yaml}"
    PROTOCOLS="${3:-LEACH,HEED,PEGASIS,SEP}"
    REPS="${4:-100}"

    docker run --rm \
        -v "$RESULTS_DIR:/workspace/results" \
        -v "$CONFIGS_DIR:/workspace/configs" \
        "$IMAGE" compare \
            --config    "$CONFIG"    \
            --protocols "$PROTOCOLS" \
            --reps      "$REPS"      \
            --output    /workspace/results
    exit 0
fi

# ── Shell ─────────────────────────────────────────────────────────────────────
if [[ "$CMD" == "shell" ]]; then
    docker run --rm -it \
        -v "$RESULTS_DIR:/workspace/results" \
        -v "$CONFIGS_DIR:/workspace/configs" \
        --entrypoint /bin/bash \
        "$IMAGE"
    exit 0
fi

# ── Test ─────────────────────────────────────────────────────────────────────
if [[ "$CMD" == "test" ]]; then
    docker run --rm \
        -v "$PROJECT_DIR:/opt/wsn_framework" \
        --entrypoint python3 \
        "$IMAGE" -m pytest /opt/wsn_framework/tests/ -v
    exit 0
fi

echo "Usage: $0 [build|compare|shell|test]"
exit 1
