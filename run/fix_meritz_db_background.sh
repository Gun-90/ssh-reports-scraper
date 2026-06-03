#!/bin/bash

# 메리츠증권 리포트 PDF URL 보정 스크립트 백그라운드 실행용 쉘
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

SCRIPT_NAME="run/fix_meritz_db.py"
LOG_FILE="fix_meritz_background.log"

echo "--------------------------------------------------"
echo "MERITZ Stock Report Correction starting in background..."
echo "Script: $SCRIPT_NAME"
echo "Log: $LOG_FILE"
echo "--------------------------------------------------"

# 백그라운드 실행 (uv run 권장, shebang 있으므로 python3 생략)
if command -v uv &> /dev/null
then
    nohup uv run $SCRIPT_NAME > $LOG_FILE 2>&1 &
else
    nohup python3 $SCRIPT_NAME > $LOG_FILE 2>&1 &
fi

PID=$!
echo "Process started with PID: $PID"
echo "To check progress, run: tail -f $LOG_FILE"
echo "To stop process, run: kill $PID"
echo "--------------------------------------------------"
