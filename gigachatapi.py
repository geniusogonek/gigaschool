import os

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")


payload_base = Chat(
    messages=[
        Messages(
            role=MessagesRole.SYSTEM,
            content="Отвечай без форматирования markdown, только текст, без форматирования"
        )
    ],
)


def get_answer(text: str) -> str:
    with GigaChat(credentials=API_KEY, verify_ssl_certs=False) as giga:
        payload = payload_base.copy()
        payload.messages.append(Messages(role=MessagesRole.USER, content=text))
        response = giga.chat(payload)
        payload.messages.append(response.choices[0].message)
        return response.choices[0].message.content
