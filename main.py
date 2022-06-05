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

    db_object.execute(f"SELECT user_id from users where user_id = {message.from_user.id}")
    result = db_object.fetchone()

    if not result:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        item1 = types.KeyboardButton(f"Студент")
        item2 = types.KeyboardButton(f"Викладач")
        markup.add(item1, item2)

        sent = bot.send_message(message.chat.id,
                                f"Привіт, {message.from_user.username}!\n"
                                f"Мене створили щоб допомогти тобі відшукати свій розклад.\n"
                                f"Для початку вибери свою роль:",
                                reply_markup=markup)

        bot.register_next_step_handler(sent, set_role)


def set_role(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, input_field_placeholder="")

    if message.text == "Студент":
        role = "Студент"
        db_object.execute(f"SELECT group_name from groups order by group_name asc")
        groups = db_object.fetchall()

        for item in groups:
            markup.add(types.KeyboardButton(item[0]))

        sent = bot.send_message(message.chat.id, "Вкажіть свою групу:", reply_markup=markup)
        bot.register_next_step_handler(sent, get_group_id)

    elif message.text == "Викладач":
        role = "Викладач"

        db_object.execute(f"SELECT teacher_name from teachers order by teacher_name asc")
        teachers = db_object.fetchall()

        for item in teachers:
            markup.add(types.KeyboardButton(item[0]))

        sent = bot.send_message(message.chat.id, "Виберіть викладача:", reply_markup=markup)
        bot.register_next_step_handler(sent, get_teacher_id)

    db_object.execute(f"INSERT INTO users(user_id, user_nickname, user_role) VALUES(%s,%s,%s)",
                      (message.from_user.id, message.from_user.username, role))
    db_connection.commit()


def get_group_id(message):
    db_object.execute(f"SELECT group_id from groups where group_name = '{message.text}'")
    group_id = db_object.fetchone()
    db_object.execute(f"UPDATE users SET group_id = %s WHERE user_id = %s", (group_id, message.from_user.id))
    db_connection.commit()


def get_teacher_id(message):
    db_object.execute(f"SELECT teacher_id from teachers where teacher_name = '{message.text}'")
    teacher_id = db_object.fetchone()
    db_object.execute(f"UPDATE users SET teacher_id = %s WHERE user_id = %s", (teacher_id, message.from_user.id))
    db_connection.commit()


@bot.message_handler(commands=["menu"])
def menu(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, )
    item1 = types.KeyboardButton(f"Розклад")
    markup.add(item1)


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
