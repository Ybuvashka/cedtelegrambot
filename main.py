import os
import telebot
import logging
import psycopg2
from config import *
from flask import Flask, request
from telebot import types

bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)
logger = telebot.logger
logger.setLevel(logging.DEBUG)

db_connection = psycopg2.connect(DB_URI, sslmode="require")
db_object = db_connection.cursor()


@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username

    db_object.execute(f"SELECT user_id from users where user_id = {user_id}")
    result = db_object.fetchone()

    if not result:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton(f"Студент")
        item2 = types.KeyboardButton(f"Викладач")
        markup.add(item1, item2)

        sent = bot.send_message(message.chat.id,
                                f"Привіт, {username}!\n"
                                f"Мене створили щоб допомогти тобі відшукати свій розклад.\n"
                                f"Для початку вибери свою роль:",
                                reply_markup=markup)

        bot.register_next_step_handler(sent, get_role)


def get_role(message):
    user_id = message.from_user.id
    username = message.from_user.username

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)

    if message.text == "Студент":
        role = "Студент"
        db_object.execute(f"SELECT group_name from groups")
        groups = types.KeyboardButton(db_object.fetchall())
        markup.add(groups)
        bot.send_message(message.chat.id,groups)
    elif message.text == "Викладач":
        role = "Викладач"

    db_object.execute(f"INSERT INTO users(user_id, user_nickname, user_role) VALUES(%s,%s,%s)",
                      (user_id, username, role))
    db_connection.commit()


@server.route(f"/{BOT_TOKEN}", methods=["POST"])
def redirect_message():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=APP_URL)
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
