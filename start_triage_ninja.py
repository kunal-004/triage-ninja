#!/usr/bin/env python3
import asyncio
import logging
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_webhook_server():
    logger.info("Starting webhook server...")
    try:
        import webhook_server
        webhook_server.app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Webhook server failed: {e}")

def run_discord_bot():
    logger.info("Starting Discord bot...")
    try:
        from discord_bot import start_bot
        asyncio.run(start_bot())
    except Exception as e:
        logger.error(f"Discord bot failed: {e}")

def main():
    logger.info("Starting agent with Real Human-in-the-Loop...")
    import config

    if not config.DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not configured in .env file")
        run_webhook_server()
        return
    
    if not config.DISCORD_CHANNEL_ID:
        logger.error("DISCORD_CHANNEL_ID not configured in .env file")
        return
    
    logger.info("Discord configuration found")
    logger.info("Starting both webhook server and Discord bot...")
    
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    
    time.sleep(2)
    logger.info("Webhook server started on http://localhost:5000")
    
    try:
        run_discord_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Triage Ninja...")

if __name__ == "__main__":
    main()
