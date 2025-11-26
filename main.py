import asyncio
import os
import logging
import speech_recognition as sr

from pydub import AudioSegment
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole


logging.basicConfig(level=logging.INFO)
bot = Bot("7869826940:AAHbb4PvYl_ks7a2s9GaCQB4hoImzcnnChQ")
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
    with GigaChat(credentials="MjllMzI5MDMtMDRmYi00MDcwLWEzMWItYTYxZTEzZjZhY2RkOjFiYmE5NzNkLWIxMzItNGIyMi05NjYwLTBiMmE4ODYwOWEzZA==", verify_ssl_certs=False) as giga:
        payload.messages.append(Messages(role=MessagesRole.USER, content=text))
        response = giga.chat(payload)
        payload.messages.append(response.choices[0].message)
        await message.answer(response.choices[0].message.content)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())