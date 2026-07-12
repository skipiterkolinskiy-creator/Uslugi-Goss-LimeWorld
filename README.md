# УслугиГосс | LimeWorld RP

Telegram-бот государственных RP-услуг для Python 3.11, aiogram 3.x и BotHost. Бот работает с двумя Google-таблицами: полной базой УслугиГосс и сокращённой базой МВД.

## Что реализовано

- регистрация персонажа с фото и заявкой в staff-чат;
- вход по коду;
- кабинет гражданина, документы, штрафы, розыск;
- медкарта через заявку на одобрение;
- лицензии: авто, грузовик, мотоцикл, оружие, рыбалка, охота;
- экзамены по одному вопросу с защитой от повторных ответов;
- проверка скрина оплаты;
- админ-панель `/panel` только в staff-чате и только для `ADMIN_IDS`;
- поиск по паспорту, Telegram ID, username и части ФИО;
- редактирование полей кнопками;
- штрафы, розыск, снятие розыска, статус Жив/Мёртв;
- безопасное чтение Google Sheets при пустых или повторяющихся заголовках;
- автоматическое создание недостающих листов УслугиГосс;
- синхронизация нужных полей со старой базой МВД по названиям столбцов.

## Установка на BotHost

1. Загрузите файлы проекта на BotHost.
2. Создайте рядом с `bot.py` файл `.env` по примеру `.env.example`.
3. Положите рядом `credentials.json` сервисного аккаунта Google.
4. Выдайте сервисному аккаунту права редактора на обе Google-таблицы.
5. Установите зависимости:

```bash
pip install -r requirements.txt
```

6. Запустите:

```bash
python bot.py
```

## Переменные окружения

```text
BOT_TOKEN=PASTE_BOT_TOKEN_HERE
ADMIN_CHAT_ID=-5484097213
ADMIN_IDS=8548608434,1453946666
GOS_SPREADSHEET_ID=1JqU5Di4WFn8RC6VafQTO2GAyFNeDqKCgHrHgBxKCjKA
MVD_SPREADSHEET_ID=1e9xsZpaaXjAIQzjyD9ZbZqzxMUUiMPKNp3ElwJfVra8
GOOGLE_CREDENTIALS_FILE=credentials.json
DATA_DIR=/app/data
DB_PATH=/app/data/uslugigoss.db
```

`.env` и `credentials.json` добавлены в `.gitignore` и не должны попадать в GitHub.

## Проверка перед деплоем

```bash
python -m compileall .
python -m pytest
```

Дополнительная проверка Google-таблиц без запуска Telegram:

```bash
python check_google.py
```

Если токен был отправлен в публичный чат или репозиторий, перевыпустите его через BotFather и обновите только `.env`.
