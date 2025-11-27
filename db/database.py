from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from db.models import Schedule, User, Subject, Homework


def parse_date(date_str: str):
    formats = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"Неподдерживаемый формат даты: {date_str}")


async def create_user(session: AsyncSession, tg_id: int, grade: str):
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise ValueError(f"Пользователь с tg_id={tg_id} уже существует")
    
    new_user = User(tg_id=tg_id, grade=grade)
    session.add(new_user)
    
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise Exception(f"Ошибка при создании пользователя: {str(e)}")


async def get_user_grade(session: AsyncSession, tg_id: int) -> str | None:
    result = await session.execute(
        select(User.grade).filter_by(tg_id=tg_id)
    )
    return result.scalar_one_or_none()


async def get_schedule_by_date(session: AsyncSession, tg_id: int, date_str: str) -> list[dict]:
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    date_obj = parse_date(date_str)
    
    result = await session.execute(
        select(Schedule)
        .options(selectinload(Schedule.subject))
        .filter_by(user_id=user.id, date=date_obj)
        .order_by(Schedule.lesson_number)
    )
    schedules = result.scalars().all()
    
    return [
        {
            "lesson_number": s.lesson_number,
            "lesson": s.subject.name if s.subject else None,
            "classroom": s.subject.classroom if s.subject else None,
            "schedule_id": s.id
        }
        for s in schedules
    ]


async def get_lesson_by_date_and_number(session: AsyncSession, tg_id: int, date_str: str, lesson_number: int) -> dict | None:
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    date_obj = parse_date(date_str)
    
    result = await session.execute(
        select(Schedule)
        .options(selectinload(Schedule.subject))
        .filter_by(user_id=user.id, date=date_obj, lesson_number=lesson_number)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        return None
    
    return {
        "lesson_number": schedule.lesson_number,
        "lesson": schedule.subject.name if schedule.subject else None,
        "classroom": schedule.subject.classroom or "" + " кабинет!" if schedule.subject else None,
        "schedule_id": schedule.id
    }


async def import_schedule_from_json(session: AsyncSession, tg_id: int, schedule_data: list):
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")

    for day_data in schedule_data:
        date_obj = parse_date(day_data['date'])

        for lesson_data in day_data['lessons']:
            subject_name = lesson_data['lesson']
            classroom = lesson_data['classroom'] or None
            lesson_number = lesson_data['lesson_number']
            load_level = lesson_data.get('load_level', 5)

            result = await session.execute(
                select(Subject).filter_by(
                    user_id=user.id,
                    name=subject_name
                )
            )
            subject = result.scalar_one_or_none()
            
            if not subject:
                subject = Subject(
                    user_id=user.id,
                    name=subject_name,
                    classroom=classroom,
                    load_level=load_level
                )
                session.add(subject)
                await session.flush()
            else:
                if classroom and not subject.classroom:
                    subject.classroom = classroom
                if load_level and not subject.load_level:
                    subject.load_level = load_level

            result = await session.execute(
                select(Schedule).filter_by(
                    user_id=user.id,
                    date=date_obj,
                    lesson_number=lesson_number
                )
            )
            schedule_entry = result.scalar_one_or_none()
            
            if not schedule_entry:
                schedule_entry = Schedule(
                    user_id=user.id,
                    date=date_obj,
                    lesson_number=lesson_number,
                    subject_id=subject.id
                )
                session.add(schedule_entry)
            else:
                schedule_entry.subject_id = subject.id
    
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise Exception(f"Ошибка при сохранении данных: {str(e)}")



async def get_all_user_subjects(session: AsyncSession, tg_id: int) -> list[dict]:
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    result = await session.execute(
        select(Subject).filter_by(user_id=user.id).order_by(Subject.name)
    )
    subjects = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "classroom": s.classroom
        }
        for s in subjects
    ]


async def add_homework(session: AsyncSession, tg_id: int, date_str: str, subject_name: str, homework_text: str):
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    date_obj = parse_date(date_str)
    
    result = await session.execute(
        select(Subject).filter_by(user_id=user.id, name=subject_name)
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise ValueError(f"Предмет '{subject_name}' не найден у пользователя")
    
    result = await session.execute(
        select(Schedule).filter_by(
            user_id=user.id,
            date=date_obj,
            subject_id=subject.id
        )
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise ValueError(f"Урок '{subject_name}' на дату {date_str} не найден в расписании")
    
    result = await session.execute(
        select(Homework).filter_by(schedule_id=schedule.id)
    )
    existing_homework = result.scalar_one_or_none()
    
    if existing_homework:
        existing_homework.text = existing_homework.text + "\n" + homework_text
    else:
        homework = Homework(schedule_id=schedule.id, text=homework_text)
        session.add(homework)
    
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise Exception(f"Ошибка при сохранении домашнего задания: {str(e)}")


async def get_homework_by_date(session: AsyncSession, tg_id: int, date_str: str) -> list[dict]:
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    date_obj = parse_date(date_str)
    
    result = await session.execute(
        select(Schedule)
        .options(selectinload(Schedule.subject), selectinload(Schedule.homework))
        .filter_by(user_id=user.id, date=date_obj)
        .order_by(Schedule.lesson_number)
    )
    schedules = result.scalars().all()
    
    homework_list = []
    for schedule in schedules:
        if schedule.homework:
            for hw in schedule.homework:
                homework_list.append({
                    "lesson_number": schedule.lesson_number,
                    "subject": schedule.subject.name if schedule.subject else None,
                    "text": hw.text,
                    "homework_id": hw.id
                })
    
    return homework_list


async def get_average_load_level(session: AsyncSession, tg_id: int, date_str: str) -> float | None:
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    date_obj = parse_date(date_str)
    
    result = await session.execute(
        select(func.avg(Subject.load_level))
        .select_from(Schedule)
        .join(Subject, Schedule.subject_id == Subject.id)
        .filter(Schedule.user_id == user.id, Schedule.date == date_obj)
    )
    avg_load = result.scalar()
    
    return float(avg_load) if avg_load is not None else None


async def edit_schedule(session: AsyncSession, tg_id: int, changes: list[dict]):
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")
    
    for change in changes:
        date_obj = parse_date(change["date"])
        subject_from_name = change["subject_from"]
        subject_to_name = change["subject_to"]
        
        result = await session.execute(
            select(Subject).filter_by(user_id=user.id, name=subject_from_name)
        )
        subject_from = result.scalar_one_or_none()
        
        if not subject_from:
            raise ValueError(f"Предмет '{subject_from_name}' не найден у пользователя")
        
        result = await session.execute(
            select(Schedule).filter_by(
                user_id=user.id,
                date=date_obj,
                subject_id=subject_from.id
            )
        )
        schedule_entry = result.scalar_one_or_none()
        
        if not schedule_entry:
            raise ValueError(f"Урок '{subject_from_name}' на дату {change['date']} не найден в расписании")
        
        if subject_to_name == "---":
            schedule_entry.subject_id = None
        else:
            result = await session.execute(
                select(Subject).filter_by(user_id=user.id, name=subject_to_name)
            )
            subject_to = result.scalar_one_or_none()
            
            if not subject_to:
                subject_to = Subject(
                    user_id=user.id,
                    name=subject_to_name,
                    classroom=None
                )
                session.add(subject_to)
                await session.flush()
            
            schedule_entry.subject_id = subject_to.id
    
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise Exception(f"Ошибка при изменении расписания: {str(e)}")
