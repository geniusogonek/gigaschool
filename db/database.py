from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from db.models import Schedule, User, Subject


async def get_user_grade(session: AsyncSession, tg_id: int) -> str | None:
    result = await session.execute(
        select(User.grade).filter_by(tg_id=tg_id)
    )
    return result.scalar_one_or_none()


async def import_schedule_from_json(session: AsyncSession, tg_id: int, schedule_data: list):
    result = await session.execute(
        select(User).filter_by(tg_id=tg_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError(f"Пользователь с tg_id={tg_id} не найден")

    for day_data in schedule_data:
        date_obj = datetime.strptime(day_data['date'], '%d.%m.%Y').date()

        for lesson_data in day_data['lessons']:
            subject_name = lesson_data['lesson']
            classroom = lesson_data['classroom'] or None
            lesson_number = lesson_data['lesson_number']

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
                    classroom=classroom
                )
                session.add(subject)
                await session.flush()
            else:
                if classroom and not subject.classroom:
                    subject.classroom = classroom

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
