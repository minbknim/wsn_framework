#!/usr/bin/env bash
# scripts/run_compare.sh — Docker 컨테이너 안에서 비교 실험 실행
set -euo pipefail

CONFIG="${1:-/workspace/configs/default_scenario.yaml}"
PROTOCOLS="${2:-LEACH,HEED,PEGASIS,SEP}"
REPS="${3:-100}"
OUTPUT="/workspace/results"

echo "========================================"
echo "  WSN Framework — Protocol Comparison"
echo "========================================"
echo "  Config    : $CONFIG"
echo "  Protocols : $PROTOCOLS"
echo "  Reps      : $REPS"
echo "  Output    : $OUTPUT"
echo "========================================"

python3 -m wsn_framework.cli compare \
    --config    "$CONFIG"    \
    --protocols "$PROTOCOLS" \
    --reps      "$REPS"      \
    --output    "$OUTPUT"

echo ""
echo "✓  완료. 결과 파일:"
ls -lh "$OUTPUT"/*.csv "$OUTPUT"/*.json 2>/dev/null || true
ls -lh "$OUTPUT"/figures/*.png 2>/dev/null || true
