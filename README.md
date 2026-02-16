# quiz_platform (Django)

Инструкции по запуску и созданию суперпользователя.

1) Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate  # или `.venv\Scripts\activate` на Windows
pip install -r requirements.txt
```

Примечание: для генерации QR-кодов требуется библиотека `qrcode` с поддержкой PIL. В requirements уже добавлен `qrcode[pil]`. Вы также можете установить отдельно:

```bash
pip install "qrcode[pil]"
```

2) Примените миграции и создайте суперпользователя:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

3) Запустите сервер разработки:

```bash
python manage.py runserver
```

Добавление Django Channels (WebSocket):

1) Установите зависимости (в requirements уже добавлен `channels`):

```bash
pip install -r requirements.txt
```

2) В `quiz_platform/settings.py` добавлен `ASGI_APPLICATION = 'quiz_platform.asgi.application'` и конфигурация `CHANNEL_LAYERS` для `InMemoryChannelLayer` (подходящая для разработки).

3) В проекте добавлены `quiz_platform/asgi.py`, `quiz/consumers.py` и `quiz/routing.py`. WebSocket-путь:

```
ws/game/<game_id>/
```

4) Для запуска с Channels используйте ASGI-сервер, например `uvicorn`:

```bash
pip install uvicorn
uvicorn quiz_platform.asgi:application --reload
```

Файлы с моделями и админом:

- [quiz/models.py](quiz/models.py)
- [quiz/admin.py](quiz/admin.py)
- [quiz_platform/settings.py](quiz_platform/settings.py)

Статические файлы и WhiteNoise

- Для продакшена выполните `collectstatic` и настройте WhiteNoise (в `settings.py` уже включён `WhiteNoiseMiddleware` и `STATICFILES_STORAGE`).
- Команды:

```bash
python manage.py collectstatic --noinput
```

- Если вы используете Docker / Docker Compose, `Dockerfile` выполняет `collectstatic` при билде. В окружении без Docker: настроить веб-сервер (nginx) для отдачи `/static/` или использовать WhiteNoise (для простого развёртывания).

Видео-встраивание (VK)

- В модели `Game` добавлено поле `video_url` (редактируйте в Django admin для каждой игры).
- Как получить embed URL из VK:
	1. Откройте страницу видео в VK.
	2. Нажмите «Поделиться» → «Встроить» / «Embed» (или найдите опцию «Код для вставки»).
	3. Скопируйте HTML-код для вставки; внутри него найдите атрибут `src="..."` в теге `iframe`.
	4. Вставьте только URL из `src` в поле `Video URL` для игры (например `https://vk.com/video_ext.php?oid=...&id=...&hash=...`).
	5. Сохраните запись — шаблоны `stream` и `play` будут использовать этот URL в `iframe`.

Примечание: обычно достаточно значения `src`. Если плеер не работает из-за ограничений встраивания, рассмотрите использование другого источника видео.

Docker Compose — быстрый запуск для теста/продакшн

1) Убедитесь, что на хосте установлены `docker` и `docker-compose` (или Docker Desktop).

2) Скопируйте пример файла окружения [/.env.example](.env.example) в корне проекта в файл `.env` и отредактируйте переменные (особенно `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`):

```bash
cp .env.example .env
# затем отредактируйте .env
```

3) Поднять сервисы и собрать образы:

```bash
docker-compose up --build
```

Первый запуск выполнит миграции и `collectstatic` внутри контейнера (см. `docker-entrypoint.sh`). Daphne будет слушать порт `8000` и проксироваться наружу `docker-compose` (http://localhost:8000).

4) Создать суперпользователя (если нужно):

```bash
docker-compose run --rm web python manage.py createsuperuser
```

5) Остановить и удалить контейнеры/тома:

```bash
docker-compose down
```

Советы по продакшену
- Для продакшена в `.env` установите `DJANGO_DEBUG=False` и надёжный `DJANGO_SECRET_KEY`.
- Замените SQLite на PostgreSQL (пример `DATABASE_URL` в `.env.example`).
- Для каналов WebSocket используйте Redis (`REDIS_URL`), не InMemory.
- Настройте обратный прокси (nginx) и TLS/HTTPS перед выставлением проекта в интернет.

Если хотите, могу автоматически собрать и запустить `docker-compose` локально, прогнать миграции и создать тестовые данные.
