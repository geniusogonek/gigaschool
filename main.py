import asyncio
import os
import logging
import speech_recognition as sr

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import BaseFilter

from pydub import AudioSegment

from dotenv import load_dotenv

from db.core import init_db, get_session_maker
from db.database import import_schedule_from_json, get_user_grade
from parse_files.parse_excel import parse_schedule_excel
from gigachatapi import get_answer


class DocumentTypeFilter(BaseFilter):
    def __init__(self, extensions: list[str]):
        self.extensions = [ext.lower() for ext in extensions]

    async def __call__(self, message: Message) -> bool:
        if not message.document or not message.document.file_name:
            return False
        file_ext = message.document.file_name.split('.')[-1].lower()
        return file_ext in self.extensions


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()


engine = None
SessionMaker = None


@dp.message(DocumentTypeFilter(["xlsx", "xls"]))
async def get_document(message: Message):
    file = await bot.get_file(message.document.file_id)
    ext = message.document.file_name.split(".")[-1]
    filename = f"{message.from_user.id}.{ext}"
    await bot.download_file(file.file_path, filename)



    async with SessionMaker() as session:
        grade = await get_user_grade(session, message.from_user.id)
        data = parse_schedule_excel(filename, grade)
        print(data)
        await import_schedule_from_json(session, tg_id=message.from_user.id, schedule_data=data)

    if os.path.exists(filename):
        os.remove(filename)


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

    logging.info(f"{message.from_user.username}, {message.from_user.id}: {text}")
    await message.answer(get_answer(text))


async def main():
    global engine, SessionMaker
    engine = await init_db(POSTGRES_URL)
    SessionMaker = get_session_maker(engine)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())