import asyncio
import os
import logging
from json import loads
from datetime import datetime
from dotenv import load_dotenv

import aio_pika
from aiogram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bot = Bot(BOT_TOKEN)


async def parse_datetime(datetime_str: str) -> datetime:
    try:
        return datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
    except ValueError as e:
        logger.error(f"Failed to parse datetime: {datetime_str}, error: {e}")
        raise


async def send_notification(tg_id: int, text: str):
    try:
        await bot.send_message(tg_id, f"⏰ Напоминание!\n\n{text}")
        logger.info(f"Notification sent to user {tg_id}")
    except Exception as e:
        logger.error(f"Failed to send notification to {tg_id}: {e}")


async def schedule_notification(tg_id: int, target_datetime: datetime, text: str):
    now = datetime.now()
    delay = (target_datetime - now).total_seconds()
    
    if delay < 0:
        logger.warning(f"Notification time has already passed for user {tg_id}")
        await bot.send_message(tg_id, "❌ Время для этого напоминания уже прошло.")
        return
    
    logger.info(f"Scheduling notification for user {tg_id} in {delay} seconds")
    await asyncio.sleep(delay)
    await send_notification(tg_id, text)


async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            data = loads(message.body.decode())
            tg_id = data["tg_id"]
            datetime_str = data["datetime"]
            text = data["text"]
            
            logger.info(f"Processing notification: {data}")
            
            target_datetime = await parse_datetime(datetime_str)
            
            # Запускаем задачу в фоне
            asyncio.create_task(schedule_notification(tg_id, target_datetime, text))
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")


async def main():
    logger.info("Starting notification worker...")
    
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        
        queue = await channel.declare_queue("notifications", durable=True)
        
        logger.info("Connected to RabbitMQ, waiting for messages...")
        
        await queue.consume(process_message)
        
        await asyncio.Future()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if connection:
            await connection.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
