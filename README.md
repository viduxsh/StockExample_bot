# StockExample_bot
A stock example telegram bot.

# [StockExample_bot](https://github.com/viduxsh/StockExample_bot)

[![LICENSE](https://img.shields.io/badge/license-MIT-lightgrey.svg)](https://github.com/viduxsh/StockExample_bot/blob/main/LICENSE)

# Telegram Bot Template Setup

This guide will walk you through setting up and running your Telegram Bot using Docker.

## Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed.
- [Docker Compose](https://docs.docker.com/compose/install/) installed.
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather).

## Installation Steps

1. **Clone or copy the project files** to your desired directory.

2. **Configure Environment Variables**:
   - Copy the `.env.example` file and rename it to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Open the `.env` file and replace `your_bot_token_here` with the token you got from BotFather.
   - You can also set `ADMIN_IDS` (comma separated Telegram user IDs) to receive automatic startup and shutdown notifications from the bot.

3. **Build and Run the Docker Container**:
   - Open a terminal in the project directory.
   - Run the following command to start the bot in the background:
     ```bash
     docker-compose up -d --build
     ```

4. **Check Logs (Optional)**:
   - To verify that the bot is running properly, you can check the logs using:
     ```bash
     docker-compose logs -f
     ```

5. **Stop the Bot**:
   - To stop the bot, use:
     ```bash
     docker-compose down
     ```

## Updating the Bot (Aggiornamento del Bot)

If you modify the Python code (e.g., `bot.py`) or install new packages in `requirements.txt`, you need to rebuild the Docker image to apply the changes:

1. Stop the current bot and rebuild the image:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```
2. Any data saved by the bot (like `messages.txt` in the `data/` folder) will **not** be lost, because it is mapped to a local volume.
