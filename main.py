import os
import telebot
import logging
import psycopg2
import calendar
from config import *
from flask import Flask, request
from telebot import types
from datetime import date, timedelta

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
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    if message.text == "Студент":
        role = "Студент"
        db_object.execute(f"SELECT group_name from groups order by group_name desc")
        groups = db_object.fetchall()

        for item in groups:
            markup.add(types.KeyboardButton(item[0]))

        sent = bot.send_message(message.chat.id, f"Вкажіть свою групу:", reply_markup=markup)
        bot.register_next_step_handler(sent, get_group_id)

    elif message.text == "Викладач":
        role = "Викладач"

        db_object.execute(f"SELECT teacher_name from teachers order by teacher_name asc")
        teachers = db_object.fetchall()

        for item in teachers:
            markup.add(types.KeyboardButton(item[0]))

        sent = bot.send_message(message.chat.id, f"Виберіть викладача:", reply_markup=markup)
        bot.register_next_step_handler(sent, get_teacher_id)

    db_object.execute(f"INSERT INTO users(user_id, user_nickname, user_role) VALUES(%s,%s,%s)",
                      (message.from_user.id, message.from_user.username, role))
    db_connection.commit()


def get_group_id(message):
    db_object.execute(f"SELECT group_id from groups where group_name = '{message.text}'")
    group_id = db_object.fetchone()
    db_object.execute(f"UPDATE users SET group_id = %s WHERE user_id = %s", (group_id, message.from_user.id))
    db_connection.commit()
    menu(message)


def get_teacher_id(message):
    db_object.execute(f"SELECT teacher_id from teachers where teacher_name = '{message.text}'")
    teacher_id = db_object.fetchone()
    db_object.execute(f"UPDATE users SET teacher_id = %s WHERE user_id = %s", (teacher_id, message.from_user.id))
    db_connection.commit()
    menu(message)


@bot.message_handler(commands=["menu"])
def menu(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    item1 = types.KeyboardButton(f"Розклад")
    item2 = types.KeyboardButton(f"Профіль")
    item3 = types.KeyboardButton(f"Поділитись")
    item4 = types.KeyboardButton(f"Будильник")
    item5 = types.KeyboardButton(f"Редагувати профіль")

    markup.add(item1, item2, item3, item4, item5)

    sent = bot.send_message(message.chat.id, f"Що вас цікавить?", reply_markup=markup)
    bot.register_next_step_handler(sent, menu_check)


def menu_check(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)

    if message.text == "Розклад":
        item1 = types.KeyboardButton(f"Сьогодні")
        item2 = types.KeyboardButton(f"Завтра")
        item3 = types.KeyboardButton(f"На тиждень")
        item4 = types.KeyboardButton(f"Назад")

        markup.add(item1, item2, item3, item4)

        sent = bot.send_message(message.chat.id, f"Виберіть один з варіантів:", reply_markup=markup)
        bot.register_next_step_handler(sent, schedule_check)

    elif message.text == "Профіль":
        sent = bot.send_message(message.chat.id, f"Що вас цікавить?")
    elif message.text == "Поділитись":
        sent = bot.send_message(message.chat.id, f"Що вас цікавить?")
    elif message.text == "Будильник":
        sent = bot.send_message(message.chat.id, f"Що вас цікавить?")
    elif message.text == "Редагувати профіль":
        db_object.execute(f"delete from users where user_id = {message.from_user.id}")
        db_connection.commit()
        start(message)


def get_fk_id(message):
    db_object.execute(f"SELECT user_role, teacher_id, group_id from users where user_id = {message.from_user.id}")
    result = db_object.fetchall()

    for row in result:
        user_role = row[0]
        teacher_id = row[1]
        group_id = row[2]

    if user_role == "Студент":
        first_param = f"teachers.teacher"
        second_param = f"groups.group"

        return first_param, second_param, group_id
    else:
        first_param = f"groups.group"
        second_param = f"teachers.teacher"

        return first_param, second_param, teacher_id


@bot.message_handler(commands=["today"])
def today(message):
    first_param, second_param, fk_id = get_fk_id(message)
    sent = ''

    db_object.execute(
        f"select subjects.subject_number, subjects.subject_name, subjects.subject_audience, {first_param}_name from subjects "
        f"join teachers_subjects on subjects.subject_id = teachers_subjects.subject_id "
        f"join teachers on teachers.teacher_id = teachers_subjects.teacher_id "
        f"join groups_subjects on subjects.subject_id = groups_subjects.subject_id "
        f"join groups on groups.group_id = groups_subjects.group_id "
        f"where {second_param}_id = %s and subjects.subject_weekday =%s order by subjects.subject_number asc",
        (fk_id, calendar.day_name[date.today().weekday()])
    )
    result = db_object.fetchall()

    if not result:
        message = bot.send_message(message.chat.id, f"Сьогодні у вас не має пар!")
    else:
        for row in result:
            sent += f"{row[0]} пара\n{row[1]}\nАудиторія: {row[2]}\n{row[3]}\n\n"
        message = bot.send_message(message.chat.id, sent)

    bot.register_next_step_handler(message, schedule_check)


def schedule_check(message):

    tomorrow_date = date.today() + timedelta(days=1)

    if message.text == "Сьогодні":
        today(message)

    elif message.text == "Завтра":
            db_object.execute(
                f"select subjects.subject_number, subjects.subject_name, subjects.subject_audience, groups.group_name from subjects "
                f"join teachers_subjects on subjects.subject_id = teachers_subjects.subject_id "
                f"join teachers on teachers.teacher_id = teachers_subjects.teacher_id "
                f"join groups_subjects on subjects.subject_id = groups_subjects.subject_id "
                f"join groups on groups.group_id = groups_subjects.group_id "
                f"where teachers.teacher_id = %s and subjects.subject_weekday =%s order by subjects.subject_number asc",
                (user_fk, calendar.day_name[tomorrow_date.weekday()])
            )
            result = db_object.fetchall()

            if not result:
                sent = bot.send_message(message.chat.id, f"Завтра у вас не має пар!")
            else:
                for row in result:
                    sent = bot.send_message(message.chat.id, f"{row[0]} пара\n"
                                                             f"{row[1]}\n"
                                                             f"Аудиторія: {row[2]}\n"
                                                             f"Група: {row[3]}"
                                            )

            bot.register_next_step_handler(sent, schedule_check)

    elif message.text == "На тиждень":
        if (user_fk != None):
            sent = bot.send_message(message.chat.id, f"{week_schedule(message)}", parse_mode="Markdown")
            bot.register_next_step_handler(sent, schedule_check)
        elif (user_fk != None):
            sent = bot.send_message(message.chat.id, )

    elif message.text == "Назад":
        menu(message)


@bot.message_handler(commands=["week"])
def week_schedule(message):
    user_fk_id = get_fk_id(message)

    sent = ''
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    for i, j in enumerate(range(len(weekdays) - 1)):
        db_object.execute(
            f"select subjects.subject_number, subjects.subject_name, subjects.subject_audience, groups.group_name "
            f"from subjects "
            f"join teachers_subjects on subjects.subject_id = teachers_subjects.subject_id "
            f"join teachers on teachers.teacher_id = teachers_subjects.teacher_id "
            f"join groups_subjects on subjects.subject_id = groups_subjects.subject_id "
            f"join groups on groups.group_id = groups_subjects.group_id "
            f"where teachers.teacher_id = %s and  subjects.subject_weekday = %s"
            f"order by subjects.subject_weekday,subjects.subject_number asc ", (user_fk_id, weekdays[i])
        )
        result = db_object.fetchall()

        if result:
            sent += f"\n{weekdays[j]}\n"
            for row in result:
                sent += f"{row[0]} пара \n{row[1]}\n аудиторія: {row[2]}\n група: {row[3]}\n\n"

    return sent


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
