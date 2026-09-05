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

# 포트를 실제로 점유 중인 프로세스의 PID를 반환한다 (없으면 빈 문자열).
#
# 왜 필요한가: `npm run dev`는 vite를 자식 프로세스(node.exe)로 띄우는데,
# git bash의 `nohup ... &`가 기록하는 $!는 그 부모(npm) PID다. Windows에서는
# 부모를 죽여도 자식 node 프로세스가 안 죽고 포트를 계속 점유하는 경우가 있다.
# 그래서 PID 파일만 믿지 않고, 실제로 포트를 리스닝 중인 프로세스를 조회해서
# 상태 확인(status)과 중지(stop) 양쪽에서 진실의 근원(source of truth)으로 쓴다.
port_pid() {
  local port="$1"
  powershell -NoProfile -Command \
    "(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)" \
    2>/dev/null | tr -d '\r'
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
    # --reload-dir app: 기본값(현재 폴더 전체)으로 두면 .venv(수만 개 .py 파일),
    # data/(업로드·ChromaDB 파일), .fastembed_cache/까지 감시 대상이 된다.
    # 우리 코드는 app/ 아래에만 있으므로 거기만 감시하도록 좁힌다.
    nohup uv run uvicorn app.main:app --reload --reload-dir app --port "$BACKEND_PORT" \
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
  local port="$2"
  local pid_file="$PID_DIR/$name.pid"
  local stopped=""

  if is_running "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"
    kill "$pid" 2>/dev/null || true
    stopped="$pid"
  fi
  rm -f "$pid_file"

  # PID 파일로 못 죽인 잔여 프로세스(예: npm의 자식 node.exe)가 포트를 계속
  # 점유하고 있을 수 있으므로, 실제 포트 리스너를 다시 확인해서 마저 정리한다.
  sleep 0.3
  local leftover
  leftover="$(port_pid "$port")"
  if [[ -n "$leftover" ]]; then
    powershell -NoProfile -Command "Stop-Process -Id $leftover -Force" >/dev/null 2>&1
    stopped="${stopped:+$stopped, }$leftover(잔여)"
  fi

  if [[ -n "$stopped" ]]; then
    echo "[$name] 중지됨 (PID $stopped)"
  else
    echo "[$name] 실행 중이 아닙니다."
  fi
}

status_one() {
  local name="$1"
  local port="$2"
  local pid
  pid="$(port_pid "$port")"
  if [[ -n "$pid" ]]; then
    echo "[$name] 실행 중 (PID $pid, 포트 :$port)"
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
      backend) stop_one backend "$BACKEND_PORT" ;;
      frontend) stop_one frontend "$FRONTEND_PORT" ;;
      all) stop_one backend "$BACKEND_PORT"; stop_one frontend "$FRONTEND_PORT" ;;
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
