import asyncio
import os
import logging
import speech_recognition as sr

from pydub import AudioSegment
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

payload = Chat(
    messages=[
        Messages(
            role=MessagesRole.SYSTEM,
            content="Отвечай без форматирования markdown, только текст, без форматирования"
        )
    ],
)



@dp.message()
async def start(message: Message):
    if message.voice:
        file = await message.bot.get_file(message.voice.file_id)
        ogg_path = f"{message.from_user.id}.ogg"
        wav_path = f"{message.from_user.id}.wav"
        await message.bot.download_file(file.file_path, ogg_path)

        audio = AudioSegment.from_file(ogg_path, format="ogg")
        audio.export(wav_path, format="wav")

        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = r.record(source)

        for f in (ogg_path, wav_path):
            if os.path.exists(f):
                os.remove(f)

        text = r.recognize_google(audio_data, language="ru-RU")
    else:
        text = message.text
    print(message.from_user.username, ": ", text)
    with GigaChat(credentials=API_KEY, verify_ssl_certs=False) as giga:
        payload.messages.append(Messages(role=MessagesRole.USER, content=text))
        response = giga.chat(payload)
        payload.messages.append(response.choices[0].message)
        await message.answer(response.choices[0].message.content)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())