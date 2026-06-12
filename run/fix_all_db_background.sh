#!/bin/bash

# 전체 증권사 리포트 PDF URL 보정 스크립트 백그라운드 실행용 쉘
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

SCRIPT_NAME="run/fix_all_db.py"
LOG_FILE="fix_all_background.log"

echo "--------------------------------------------------"
echo "ALL Stock Report Correction starting in background..."
echo "Script: $SCRIPT_NAME"
echo "Log: $LOG_FILE"
echo ""
echo "Supports: see FIRM_FIXES in fix_all_db.py"
echo "--------------------------------------------------"

# 백그라운드 실행 (전체 실행, nohup에선 questionary 불가능하므로 "all" 인자 전달)
if command -v uv &> /dev/null
then
    nohup uv run $SCRIPT_NAME all > $LOG_FILE 2>&1 &
else
    nohup python3 $SCRIPT_NAME all > $LOG_FILE 2>&1 &
fi

PID=$!
echo "Process started with PID: $PID"
echo "To check progress, run: tail -f $LOG_FILE"
echo "To stop process, run: kill $PID"
echo "--------------------------------------------------"
