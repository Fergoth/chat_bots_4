import logging
import os
import random

import redis
from dotenv import load_dotenv
from telegram import Bot, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

from utilities import check_answer, load_questions

logger = logging.getLogger("telegram_debug")

CHOOSING, ANSWERING = range(2)


def handle_new_question_request(update: Update, context: CallbackContext) -> None:
    reply_markup = context.bot_data["reply_markup"]
    user_id = update.message.from_user.id
    redis_client = context.bot_data["redis_client"]
    questions = context.bot_data["questions"]
    if redis_client.exists(user_id):
        update.message.reply_text(
            f"Вы не ответили на предыдущий вопрос:{redis_client.get(user_id)}",
            reply_markup=reply_markup,
        )
    else:
        new_question = random.choice(list(questions.keys()))
        redis_client.set(user_id, new_question)
        update.message.reply_text(new_question)
    return ANSWERING


def handle_solution_attempt(update: Update, context: CallbackContext) -> None:
    reply_markup = context.bot_data["reply_markup"]
    user_id = update.message.from_user.id
    redis_client = context.bot_data["redis_client"]
    questions = context.bot_data["questions"]
    if redis_client.exists(user_id):
        question = redis_client.get(user_id)
        answer = questions[question]
        if check_answer(update.message.text, answer):
            update.message.reply_text(
                "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»",
                reply_markup=reply_markup,
            )
            redis_client.delete(user_id)
            return CHOOSING
        else:
            update.message.reply_text(
                "Неправильно… Попробуешь ещё раз?", reply_markup=reply_markup
            )


def handle_give_up(update: Update, context: CallbackContext) -> None:
    reply_markup = context.bot_data["reply_markup"]
    user_id = update.message.from_user.id
    redis_client = context.bot_data["redis_client"]
    questions = context.bot_data["questions"]
    if redis_client.exists(user_id):
        question = redis_client.get(user_id)
        answer = questions[question]
        update.message.reply_text(
            f"Правильный ответ: {answer}. Чтобы продолжить нажми «Новый вопрос»",
            reply_markup=reply_markup,
        )
        redis_client.delete(user_id)
    else:
        update.message.reply_text(
            "У вас нет активных вопросов. Нажмите «Новый вопрос»",
            reply_markup=reply_markup,
        )
    return CHOOSING


def start(update: Update, context: CallbackContext) -> None:
    reply_markup = context.bot_data["reply_markup"]
    update.message.reply_text("Привет, я бот-викторина.", reply_markup=reply_markup)
    return CHOOSING


def cancel(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Викторина завершена.")
    return ConversationHandler.END


class TelegramLogsHandler(logging.Handler):
    def __init__(self, chat_id, tg_token):
        super().__init__()
        self.chat_id = chat_id
        self.bot = Bot(token=tg_token)

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.send_message(chat_id=self.chat_id, text=log_entry)


def main():
    load_dotenv()
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")
    redis_db = int(os.environ.get("REDIS_DB_TG", "1"))
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        encoding="utf-8",
        decode_responses=True,
    )
    tg_debug_token = os.environ.get("TELEGRAM_DEBUG_BOT_TOKEN")
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    if tg_debug_token:
        logger.addHandler(TelegramLogsHandler(chat_id, tg_debug_token))
    logger.setLevel(logging.INFO)
    tg_token = os.environ["TELEGRAM_BOT_TOKEN"]
    updater = Updater(token=tg_token)
    dispatcher = updater.dispatcher

    keyboard = [
        [
            KeyboardButton("Новый вопрос"),
            KeyboardButton("Сдаться"),
        ],
        [KeyboardButton("Мой счёт")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(
                    Filters.regex("^Новый вопрос$"), handle_new_question_request
                ),
            ],
            ANSWERING: [
                MessageHandler(Filters.regex("^Сдаться$"), handle_give_up),
                MessageHandler(Filters.text, handle_solution_attempt),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.bot_data["questions"] = load_questions("quiz-questions")
    dispatcher.bot_data["redis_client"] = redis_client
    dispatcher.bot_data["reply_markup"] = reply_markup
    logger.info("Телеграм Бот quiz запущен")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
