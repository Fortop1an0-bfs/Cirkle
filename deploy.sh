#!/bin/sh
# Деплой Cirkle на шаред-хостинг (Reg.ru и т.п.).
# Использование:
#   sh deploy.sh <BOT_TOKEN>      # первый раз: создаст .env с токеном
#   sh deploy.sh                  # повторно: если .env уже есть
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3.12}"

echo ">>> Папка проекта: $PROJECT_DIR"
echo ">>> Python: $PYTHON ($($PYTHON --version 2>&1))"

# 1. venv
if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
    echo ">>> Создаю виртуальное окружение..."
    "$PYTHON" -m venv "$PROJECT_DIR/.venv"
fi

# 2. зависимости
echo ">>> Ставлю зависимости..."
"$PROJECT_DIR/.venv/bin/python" -m pip install -q --upgrade pip
"$PROJECT_DIR/.venv/bin/python" -m pip install -q -r "$PROJECT_DIR/requirements.txt"

# 3. .env
if [ -n "$1" ]; then
    echo ">>> Записываю .env (токен из аргумента)..."
    cat > "$PROJECT_DIR/.env" <<EOF
BOT_TOKEN=$1
INTERVAL_MINUTES=30
TZ=Asia/Vladivostok
EOF
    chmod 600 "$PROJECT_DIR/.env"
fi
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "!!! Нет .env и не передан токен. Запусти: sh deploy.sh <BOT_TOKEN>"
    exit 1
fi

# 4. cron: вотчдог каждые 2 минуты + автозапуск после ребута
chmod +x "$PROJECT_DIR/run.sh"
RUN="$PROJECT_DIR/run.sh"
( crontab -l 2>/dev/null | grep -v "$RUN" ; \
  echo "*/2 * * * * $RUN >/dev/null 2>&1" ; \
  echo "@reboot $RUN >/dev/null 2>&1" ) | crontab -
echo ">>> Cron установлен:"
crontab -l | grep "cirkle" || true

# 5. перезапуск бота
echo ">>> (Пере)запускаю бота..."
"$RUN" stop || true
"$RUN"
sleep 2
echo ">>> Статус:"
"$RUN" status
echo ">>> Логи: tail -f $PROJECT_DIR/cirkle.log"
