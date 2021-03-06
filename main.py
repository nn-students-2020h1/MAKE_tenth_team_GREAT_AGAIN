# coding=utf8
# semaev branch
import os
import logging
import traceback
import requests
import json
from datetime import date, timedelta, datetime
import csv
from url_parser import UrlParser

get_protocol = UrlParser.get_url_protocol
http_replace = UrlParser.http_replace
http_add_space = UrlParser.http_add_space
split_by_space = UrlParser.split_by_space
url_domain = UrlParser.get_url_domain
url_page = UrlParser.get_url_page

from telegram import Bot, Update
from telegram.ext import CallbackContext, CommandHandler, Filters, MessageHandler, Updater

from config import msg_logs_file
import settings
import re


logger = logging.getLogger(__name__)


def download_last_covid_report(report_date=date.today()):
    github_folder = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports'
    response, report_url = None, None
    while response is None or response.status_code == 404:
        report_url = f"{github_folder}/{report_date.strftime('%m-%d-%Y')}.csv"
        response = requests.get(report_url)
        report_date -= timedelta(days=1)
    logger.debug(f"Отчёт удачно скачан по ссылке {report_url}")
    with open("covid-19.csv", "wb") as file:
        file.write(response.content)


def sort_and_rewrite_covid_report():
    with open('covid-19.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        report = list(reader)
    result = sorted(report, key=lambda row: int(row["Confirmed"]), reverse=True)
    with open('covid-19.csv', 'w') as file:
        writer = csv.DictWriter(file, fieldnames)
        writer.writeheader()
        for row in result:
            writer.writerow(row)


def rewrite_covid_report_with_countries():
    country_field = "Country_Region"
    required_fields = ["Confirmed", "Deaths", "Recovered", "Active"]
    all_fields = [country_field] + required_fields
    with open('covid-19.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        input_data = list(reader)
    required_fields = [field for field in required_fields if field in fieldnames]

    countries = dict()
    for row in input_data:
        if row[country_field] not in countries:
            countries[row[country_field]] = [0 for field in required_fields]
        for i, required_field in enumerate(required_fields):
            countries[row[country_field]][i] += int(row[required_field])

    output_data = [[country] + fields for country, fields in countries.items()]
    output_data = [{all_fields[i]: row[i] for i in range(len(row))} for row in output_data]
    print(output_data)
    with open('covid-19.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=[country_field] + required_fields)
        writer.writeheader()
        for row in output_data:
            writer.writerow(row)


def shortMsgInfo(update):
    message = update.message
    data = {
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,

        "text": message.text,

        "from_id": message.from_user.id,
        "chat_id": message.chat.id,
        "language": message.from_user.language_code,
    }
    return data

def sort_covid_by_date():
    with open('covid-19.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        report = list(reader)
    result = sorted(report, key=lambda row: row["Last_Update"], reverse=True)
    with open('covid-19.csv', 'w') as file:
        writer = csv.DictWriter(file, fieldnames)
        writer.writeheader()
        for row in result:
            writer.writerow(row)

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def msg_logging(func):
    """Log Messages caused by Updates."""
    def wrapper(update, context):
        logger.debug(list(shortMsgInfo(update).values()) , extra={"func_name": func.__name__})
        func(update, context)
    return wrapper

@msg_logging
def most_popular_fact(update: Update, context: CallbackContext):
    best_fact = None
    r = requests.get("https://cat-fact.herokuapp.com/facts")
    for fact in r.json()["all"]:
        best_fact = fact if best_fact is None else best_fact
        if fact["upvotes"] > best_fact["upvotes"]:
            best_fact = fact
    update.message.reply_text(f'The most popular fact is: {best_fact["text"]}')

@msg_logging
def authors(update: Update, context: CallbackContext):
    response = requests.get("https://cat-fact.herokuapp.com/facts")
    authors = [fact["user"] for fact in response. json()["all"] if "user" in fact]
    board = dict()
    for author in authors:
        _id = author["_id"]
        board.setdefault(_id, 0)
        board[_id] += 1
    board = tuple(board.items())
    board = sorted(board, key=lambda author: author[1], reverse=True)
    author1 = list(filter(lambda author: author["_id"] == board[0][0], authors))[0]
    author2 = list(filter(lambda author: author["_id"] == board[1][0], authors))[0]
    author3 = list(filter(lambda author: author["_id"] == board[2][0], authors))[0]
    update.message.reply_text(
        f"The most popular authors are: \n\n"
        f"#1 {author1['name']['first']} {author1['name']['last']} \nNumber of posts: {board[0][1]}\n"
        f"#2 {author2['name']['first']} {author2['name']['last']} \nNumber of posts: {board[1][1]}\n"
        f"#3 {author3['name']['first']} {author3['name']['last']} \nNumber of posts: {board[2][1]}\n"
    )
@msg_logging
def corono_stats(update: Update, context: CallbackContext):
    logger.info("corono_stats")
    dates = []
    for word in update.message["text"].split():
        dates_now = re.findall(r"\d\d[-.]\d\d[-.]\d\d\d\d", word)
        dates.append(tuple(dates_now[0].split("."))) if dates_now else None
        dates_now = re.findall(r"\d\d\d\d[-.]\d\d[-.]\d\d", word)
        dates.append(tuple(reversed(dates_now[0].split(".")))) if dates_now else None
    dates = [f"{d[0]}.{d[1]}.{d[2]}" for d in dates]
    date_ = datetime.strptime(dates[0], "%d.%m.%Y") if dates else date.today()
    #func_1:download new file
    download_last_covid_report(date_)
    #func_2:rewrite new information in file
    sort_and_rewrite_covid_report()
    with open('covid-19.csv', 'r') as file:
        reader = csv.DictReader(file)
        report = list(reader)

        # dates.append(re.findall(r"\d\d\d\d[-.]\d\d[-.]\d\d", word))
    update.message.reply_text(date_.strftime("%d.%m.%Y"))
    update.message.reply_text(f"Five most popular places:\n" + "\n".join(str(row) for row in report[:5]))

@msg_logging
def corona_news(update: Update, context: CallbackContext):
    #funk_1:download new file
    download_last_covid_report()
    #funk_2:rewrite new information in file
    sort_covid_by_date()
    rewrite_covid_report_with_countries()
    with open('covid-19.csv', 'r') as file:
        reader = csv.DictReader(file)
        report = list(reader)
    update.message.reply_text("Last infections:\n" + "\n".join(str(row) for row in report[:7]))


@msg_logging
def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    update.message.reply_text(f'Привет, {update.effective_user.first_name}!')

@msg_logging
def chat_help(update: Update, context: CallbackContext):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Введи команду /start для начала. Введи команду /history для показа истории бота. Введи команду /fact для показа одного популярного факта. /corono_stats dd.mm.yyy or /corono_stats and /corono_news - отличный опыт получения информации о пандемии!')

@msg_logging
def echo(update: Update, context: CallbackContext):
    """Echo the user message."""
    update.message.reply_text(update.message.text)
    urls = []
    for word in update.message["text"].split():
        parser = UrlParser(word)
        urls += parser.parse()
    update.message.reply_text(f"Найдены ссылки: {urls}") if urls else None

@msg_logging
def history(update: Update, context: CallbackContext):
    """Echo last 5 message from all users"""
    with open(msg_logs_file, "r", encoding='utf8') as file:
        last_5 = "".join(file.readlines()[-5:])
        update.message.reply_text(last_5)

def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(f"{context.error}\n{traceback.format_exc()[:-1]}")

def main():
    bot = Bot(
        token=os.getenv("TG_TOKEN"),
        base_url=os.getenv("TG_PROXY")
    )
    updater = Updater(bot=bot, use_context=True, workers=-3)

    # on different commands - answer in Telegram
    updater.dispatcher.add_handler(CommandHandler('authors', authors))
    updater.dispatcher.add_handler(CommandHandler('fact', most_popular_fact))
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('help', chat_help))
    updater.dispatcher.add_handler(CommandHandler('history', history))
    updater.dispatcher.add_handler(CommandHandler('corono_stats', corono_stats))
    updater.dispatcher.add_handler(CommandHandler('corono_news', corona_news))
    # updater.dispatcher.add_handler(CommandHandler('corono_stats', corono_stats))

    # updater.dispatcher.add_handler(CommandHandler('corona', corona))
    # on noncommand i.e message - echo the message on Telegram
    updater.dispatcher.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    updater.dispatcher.add_error_handler(error)

    logger.info('start bot')
    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
