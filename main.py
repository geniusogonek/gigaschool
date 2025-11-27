import asyncio
from json import loads
import os
import logging
import speech_recognition as sr

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import BaseFilter, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from pydub import AudioSegment

from dotenv import load_dotenv

from db.core import init_db, get_session_maker
from db.database import (
    import_schedule_from_json, get_user_grade, get_lesson_by_date_and_number, get_schedule_by_date, create_user,
    add_homework, get_homework_by_date, get_average_load_level, edit_schedule
)
from parse_files.parse_excel import parse_schedule_excel
from gigachatapi import get_answer


class RegistrationStates(StatesGroup):
    waiting_for_grade = State()


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
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

engine = None
SessionMaker = None


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    async with SessionMaker() as session:
        existing_grade = await get_user_grade(session, message.from_user.id)
        
        if existing_grade:
            await message.answer(f"Ты уже зарегистрирован. Твой класс: {existing_grade}")
            return
    
    await state.set_state(RegistrationStates.waiting_for_grade)
    await message.answer("Привет! Напиши свой класс (например, 9А или 11Б):")


@dp.message(StateFilter(RegistrationStates.waiting_for_grade))
async def process_grade(message: Message, state: FSMContext):
    grade = message.text.strip()
    
    async with SessionMaker() as session:
        await create_user(session, message.from_user.id, grade)
    
    await state.clear()
    await message.answer(f"Отлично! Твой класс: {grade}\nТеперь пришли мне свое расписание в формате Excel.")


@dp.message(DocumentTypeFilter(["xlsx", "xls"]))
async def get_document(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == RegistrationStates.waiting_for_grade:
        await message.answer("Сначала укажи свой класс!")
        return
    
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
    
    await message.answer("Молодец! Расписание успешно загружено! Теперь ты можешь задавать свои вопросы. :)")


@dp.message()
async def speak(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == RegistrationStates.waiting_for_grade:
        await message.answer("Сначала укажи свой класс!")
        return
    
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
        try:
            text = r.recognize_google(audio_data, language="ru-RU")
        except:
            return await message.answer("Не удалось распознать голос.")
    else:
        text = message.text

    logging.info(f"New message: username={message.from_user.username} id={message.from_user.id} text={text}")
    async with SessionMaker() as session:
        answer = await get_answer(session, text, message.from_user.id)
    json_data = loads(answer)
    print(json_data)
    match json_data["type"]:
        case "undetected":
            await message.answer("Извини, я немного не понимаю твой вопрос :(\nМожешь, пожалуйста, переформулировать его?")
        case "schedule":
            async with SessionMaker() as session:
                schedule = await get_schedule_by_date(session, message.from_user.id, json_data["date"])
                schedule_list = [f"{i['lesson_number']}. {i['lesson']}, {i['classroom']}каб.".replace("None", "без ") for i in schedule]

                if len(schedule_list) != 0:
                    avg_load = await get_average_load_level(session, message.from_user.id, json_data["date"])

                    if avg_load is not None:
                        if avg_load <= 4:
                            load_message = "💚 Легкий денёк! Отличное время набраться сил и заняться любимыми делами."
                        elif avg_load <= 7:
                            load_message = "💛 День с умеренной нагрузкой. Держи баланс между учёбой и отдыхом!"
                        else:
                            load_message = "❤️ Насыщенный день! Собери волю в кулак — ты справишься!"

                        await message.answer(f"Вот твое расписание:\n{'\n'.join(schedule_list)}\n\n{load_message}")
                    else:
                        await message.answer("Вот твое расписание:\n" + "\n".join(schedule_list))
                else:
                    await message.answer("К сожалению, ты пока не загрузил расписание на этот день.")
        case "lesson":
            if json_data.get("lesson_number") is not None:
                async with SessionMaker() as session:
                    lesson = await get_lesson_by_date_and_number(session, message.from_user.id, json_data["date"], json_data["lesson_number"])
                    await message.answer(f"{lesson['lesson']}, {lesson['classroom'] or 'без кабинета'}")
            else:
                await message.answer("заглушка")
        case "add_homework":
            async with SessionMaker() as session:
                try:
                    await add_homework(session, message.from_user.id, json_data["date"], json_data["subject_name"], json_data["text"])
                    await message.answer(f"✅ Домашнее задание по предмету '{json_data['subject_name']}' добавлено!")
                except:
                    await message.answer(f"В указанный день нет урока '{json_data['subject_name']}' :(")
        case "get_homework":
            async with SessionMaker() as session:
                homework = [f"{i['subject']}: {i['text']}" for i in await get_homework_by_date(session, message.from_user.id, json_data["date"])]
                if homework != []:
                    await message.answer("Вот твое домашнее задание:\n" + "\n".join(homework))
                else:
                    await message.answer("На указанный день нет домашнего задания! :)")
        case "edit_schedule":
            async with SessionMaker() as session:
                try:
                    await edit_schedule(session, message.from_user.id, json_data["changes"])
                    changes_text = []
                    for change in json_data["changes"]:
                        if change["subject_to"] == "---":
                            changes_text.append(f"• {change['subject_from']} отменён")
                        else:
                            changes_text.append(f"• {change['subject_from']} → {change['subject_to']}")
                    
                    await message.answer(f"✏️ Расписание обновлено!\n\n" + "\n".join(changes_text))
                except Exception as e:
                    await message.answer(f"Не удалось изменить расписание: {str(e)}")
        case _:
            await message.answer(str(json_data))



async def main():
    global engine, SessionMaker
    engine = await init_db(POSTGRES_URL)
    SessionMaker = get_session_maker(engine)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
