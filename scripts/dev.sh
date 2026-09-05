#!/usr/bin/env bash
# 백엔드(FastAPI/uvicorn)와 프론트엔드(Vite) 개발 서버를 관리하는 스크립트.
#
# 사용법:
#   scripts/dev.sh start   # 백엔드(:8000) + 프론트엔드(:5173) 모두 백그라운드로 시작
#   scripts/dev.sh stop    # 둘 다 중지
#   scripts/dev.sh status  # 실행 상태 + 포트 표시
#   scripts/dev.sh start backend   # 백엔드만
#   scripts/dev.sh start frontend  # 프론트엔드만
#
# PID는 scripts/.pids/ 아래에, 로그는 scripts/.logs/ 아래에 남긴다 (둘 다 gitignore 대상).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/scripts/.pids"
LOG_DIR="$ROOT_DIR/scripts/.logs"
BACKEND_PORT=8000
FRONTEND_PORT=5173

mkdir -p "$PID_DIR" "$LOG_DIR"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_backend() {
  local pid_file="$PID_DIR/backend.pid"
  if is_running "$pid_file"; then
    echo "[backend] 이미 실행 중입니다 (PID $(cat "$pid_file"), :$BACKEND_PORT)"
    return
  fi
  echo "[backend] 시작 중... http://127.0.0.1:$BACKEND_PORT"
  (
    cd "$ROOT_DIR"
    nohup uv run uvicorn app.main:app --reload --port "$BACKEND_PORT" \
      > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$pid_file"
  )
  echo "[backend] 시작됨. 접속: http://127.0.0.1:$BACKEND_PORT/docs"
}

start_frontend() {
  local pid_file="$PID_DIR/frontend.pid"
  if is_running "$pid_file"; then
    echo "[frontend] 이미 실행 중입니다 (PID $(cat "$pid_file"), :$FRONTEND_PORT)"
    return
  fi
  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    echo "[frontend] node_modules가 없습니다. 먼저 실행하세요: (cd frontend && npm install)"
    return
  fi
  echo "[frontend] 시작 중... http://127.0.0.1:$FRONTEND_PORT"
  (
    cd "$ROOT_DIR/frontend"
    nohup npm run dev -- --port "$FRONTEND_PORT" \
      > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$pid_file"
  )
  echo "[frontend] 시작됨. 접속: http://127.0.0.1:$FRONTEND_PORT"
}

stop_one() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if is_running "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"
    kill "$pid" 2>/dev/null || true
    rm -f "$pid_file"
    echo "[$name] 중지됨 (PID $pid)"
  else
    echo "[$name] 실행 중이 아닙니다."
    rm -f "$pid_file"
  fi
}

status_one() {
  local name="$1"
  local port="$2"
  local pid_file="$PID_DIR/$name.pid"
  if is_running "$pid_file"; then
    echo "[$name] 실행 중 (PID $(cat "$pid_file"), 포트 :$port)"
  else
    echo "[$name] 중지됨"
  fi
}

case "${1:-}" in
  start)
    case "${2:-all}" in
      backend) start_backend ;;
      frontend) start_frontend ;;
      all) start_backend; start_frontend ;;
      *) echo "알 수 없는 대상: ${2:-}"; exit 1 ;;
    esac
    ;;
  stop)
    case "${2:-all}" in
      backend) stop_one backend ;;
      frontend) stop_one frontend ;;
      all) stop_one backend; stop_one frontend ;;
      *) echo "알 수 없는 대상: ${2:-}"; exit 1 ;;
    esac
    ;;
  status)
    status_one backend "$BACKEND_PORT"
    status_one frontend "$FRONTEND_PORT"
    ;;
  *)
    echo "사용법: $0 {start|stop|status} [backend|frontend|all]"
    exit 1
    ;;
esac
