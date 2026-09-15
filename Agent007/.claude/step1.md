## шаг 1. Настройка окружения
# установка необходимых инструментов и библиотек: Python, MySQL, Kafka, виртуальные окружения, инструменты для статического анализа кода (pylint, flake8)

## Что сделано
# [x] Python 3.13.0 (уже был установлен в системе)
# [x] Виртуальное окружение: .venv в корне репозитория
# [x] Зависимости: requirements.txt (telethon, SQLAlchemy+aiomysql, alembic, aiokafka, pydantic-settings)
#     и requirements-dev.txt (pytest, pytest-asyncio, pytest-cov, flake8, pylint) — установлены
# [x] Статический анализ: setup.cfg (flake8, max-line-length=100), .pylintrc — оба проходят чисто
# [x] MySQL 8.4 и Kafka 3.9 (KRaft, без ZooKeeper) описаны в docker-compose.yml.
#     Локально на хост не ставятся — по требованию Promt.md о контейнеризации.
# [x] Конфигурация: .env.example -> .env, типизированный доступ через app/config.py (pydantic-settings)
# [x] Логирование: app/logging_config.py -> Log/app.log и отдельный Log/errors.log (требование Promt.md)
# [x] Проверка окружения: Agent007/scripts/check_env.py (MySQL + Kafka + Telegram)
# [x] Тесты: 20 проходят, 1 integration-тест пропускается без поднятой инфраструктуры
# [x] Файлы добавлены в Agent007.pyproj, venv подключён как интерпретатор проекта
# [x] Инфраструктура поднята: docker compose up -d, оба контейнера healthy.
#     check_env.py: MySQL 8.4.11 — OK, Kafka (1 брокер) — OK, «Environment is ready.»
#     MySQL опубликован на порту хоста 3307: 3306 занят службой Windows MySQL80.
# [x] Git-репозиторий инициализирован, первый коммит сделан

## Осталось (не блокирует шаг 1)
# [ ] Задать реальные пароли в .env (сейчас там значения-заглушки change-me).
#     Внимание: контейнер MySQL уже инициализирован с ними — смена пароля
#     требует docker compose down -v (данные будут потеряны).
# [ ] TELEGRAM_API_ID / TELEGRAM_API_HASH с https://my.telegram.org (нужны начиная с шага работы с аккаунтами)

# Status: complete
