#!/bin/sh
# Запускает Cirkle, если он ещё не работает. Используется cron-вотчдогом и @reboot.
# Команды: run.sh [start] | status | stop

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$PROJECT_DIR/.venv/bin/python"
BOT="$PROJECT_DIR/bot.py"
PIDFILE="$PROJECT_DIR/cirkle.pid"
LOG="$PROJECT_DIR/cirkle.log"

is_running() {
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

case "$1" in
    status)
        if is_running; then
            echo "RUNNING (pid $(cat "$PIDFILE"))"
        else
            echo "NOT running"
        fi
        ;;
    stop)
        if is_running; then
            kill "$(cat "$PIDFILE")" && echo "stopped"
            rm -f "$PIDFILE"
        else
            echo "was not running"
        fi
        ;;
    *)
        if is_running; then
            exit 0
        fi
        cd "$PROJECT_DIR" || exit 1
        nohup "$PY" "$BOT" >> "$LOG" 2>&1 &
        echo $! > "$PIDFILE"
        echo "started (pid $!)"
        ;;
esac
