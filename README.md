# Weekend Bot

Меняем имя с .env.example на .env и указываем `BOT_TOKEN` и `ALLOWED_USERS`. В `ALLOWED_USERS` нужно указать ID пользователей. Узнать их можно через бота @getmyid_bot

## Запуск
```bash
docker compose up -d && docker compose logs -f -t
```
