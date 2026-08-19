# Instagram → Telegram Bot

A small Telegram bot that watches messages in a Telegram group for public Instagram
post/reel URLs and downloads the available media with `yt-dlp`, then sends the
media back to the same group.

## Important

Do NOT put the Telegram bot token in the source code or GitHub.
Use the `BOT_TOKEN` environment variable.

If the token you pasted into chat is real, revoke it in BotFather and generate
a new one before deploying.

## Features

- Instagram posts
- Instagram reels
- Multiple media items when yt-dlp exposes them
- Automatic send back to the same Telegram group
- `/id` to show the current chat ID
- Optional `ALLOWED_CHAT_IDS` restriction
- Telegram webhook support for free web hosting
- Health endpoint at `/`

## Deployment on a Render-style free web service

1. Create a new GitHub repository and upload:
   - `app.py`
   - `requirements.txt`
   - `render.yaml`

2. Create a free Web Service from the repository.

3. Add environment variables:
   - `BOT_TOKEN` = your NEW bot token
   - `WEBHOOK_SECRET` = a random secret
   - `ALLOWED_CHAT_IDS` = leave blank initially
   - `MAX_FILE_MB` = `49`

4. Deploy and copy your Render HTTPS URL.

5. Set the Telegram webhook:

   `https://api.telegram.org/botYOUR_NEW_TOKEN/setWebhook?url=https://YOUR-RENDER-DOMAIN/telegram/webhook&secret_token=YOUR_SECRET`

   Do this with a browser or curl. Never commit the token/secret to GitHub.

6. Add the bot to your Telegram group.

7. For easiest operation in groups, either make the bot an admin or disable
   Telegram privacy mode for the bot in BotFather (`/setprivacy` → Disable).

8. Send `/id` in the group and copy the returned ID.

9. Put that ID into `ALLOWED_CHAT_IDS`, redeploy, and the bot will only react
   in that group.

## Limitations

- This is intended for publicly accessible Instagram URLs.
- Private, deleted, age-restricted, or login-required posts may fail.
- Instagram can change its website and anti-bot systems, so downloader support
  can occasionally break and require a newer `yt-dlp`.
- Telegram has upload limits; the bot is configured conservatively around 49 MB
  per media file.
- A free web service may sleep, so "instant" delivery is best-effort rather
  than a guaranteed SLA.

## Local test

Set environment variables and run:

`pip install -r requirements.txt`

`python app.py`

For local webhook testing, expose the service through an HTTPS tunnel and
register that public URL with Telegram.
