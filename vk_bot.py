import logging
import os
import random

import redis
import vk_api as vk
from dotenv import load_dotenv
from telegram import Bot
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkEventType, VkLongPoll
from vk_api.utils import get_random_id

from utilities import check_answer, load_questions

logger = logging.getLogger("telegram_debug")


class TelegramLogsHandler(logging.Handler):
    def __init__(self, chat_id, tg_token):
        super().__init__()
        self.chat_id = chat_id
        self.bot = Bot(token=tg_token)

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.send_message(chat_id=self.chat_id, text=log_entry)


def handle_new_question_request(event, vk_api, redis_client, questions, keyboard):
    user_id = event.user_id
    if redis_client.exists(user_id):
        message = f"Вы не ответили на предыдущий вопрос:{redis_client.get(user_id)}"
    else:
        new_question = random.choice(list(questions.keys()))
        redis_client.set(user_id, new_question)
        message = new_question
    vk_api.messages.send(
        user_id=user_id,
        message=message,
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard(),
    )


def handle_solution_attempt(event, vk_api, redis_client, questions, keyboard):
    user_id = event.user_id
    if redis_client.exists(user_id):
        question = redis_client.get(user_id)
        answer = questions[question]
        if check_answer(event.text, answer):
            message = (
                "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»",
            )
            redis_client.delete(user_id)
        else:
            message = "Неправильно… Попробуешь ещё раз?"
    else:
        message = "У вас нет активных вопросов. Нажмите «Новый вопрос»"

    vk_api.messages.send(
        user_id=user_id,
        message=message,
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard(),
    )


def handle_give_up(event, vk_api, redis_client, questions, keyboard) -> None:
    user_id = event.user_id
    if redis_client.exists(user_id):
        question = redis_client.get(user_id)
        answer = questions[question]
        message = (
            f"Правильный ответ: {answer}. Чтобы продолжить нажми «Новый вопрос»",
        )
        redis_client.delete(user_id)
    else:
        message = ("У вас нет активных вопросов. Нажмите «Новый вопрос»",)
    vk_api.messages.send(
        user_id=user_id,
        message=message,
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard(),
    )


def main():
    load_dotenv()
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")
    redis_db = int(os.environ.get("REDIS_DB_VK", "0"))
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        encoding="utf-8",
        decode_responses=True,
    )
    path_to_questions = os.environ.get("PATH_TO_QUESTIONS", "quiz-questions")
    questions = load_questions(path_to_questions)
    tg_debug_token = os.environ.get("TELEGRAM_DEBUG_BOT_TOKEN")
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    if tg_debug_token:
        logger.addHandler(TelegramLogsHandler(chat_id, tg_debug_token))
    logger.setLevel(logging.INFO)

    vk_token = os.environ["VK_TOKEN"]
    vk_session = vk.VkApi(token=vk_token)
    vk_api = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)
    logger.info("VK Бот quiz запущен")

    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("Новый вопрос", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Сдаться", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("Мой счет", color=VkKeyboardColor.PRIMARY)

    for event in longpoll.listen():
        try:
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                if event.text == "Новый вопрос":
                    handle_new_question_request(
                        event, vk_api, redis_client, questions, keyboard
                    )
                    continue
                if event.text == "Сдаться":
                    handle_give_up(event, vk_api, redis_client, questions, keyboard)
                    continue
                handle_solution_attempt(
                    event, vk_api, redis_client, questions, keyboard
                )
        except Exception as e:
            logger.exception(f"Неизвестная ошибка:{e}")


if __name__ == "__main__":
    main()
