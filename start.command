#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Сначала создайте окружение по инструкции README.md.'
  read -r '?Нажмите Enter для выхода.'
  exit 1
fi
echo 'Откройте http://127.0.0.1:8000 в браузере. Для остановки нажмите Ctrl+C.'
exec .venv/bin/python -m backend
