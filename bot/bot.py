import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import random
import schedule
import time
import threading
import os
import json
import asyncio
import logging

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load bot token from environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Sample vocabulary words (English-German)
word_list = [
    ("apple", "Apfel"),
    ("car", "Auto"),
    ("house", "Haus"),
    ("book", "Buch"),
    ("friend", "Freund"),
    ("water", "Wasser"),
    ("sun", "Sonne"),
    ("teacher", "Lehrer"),
    ("computer", "Computer"),
    ("school", "Schule"),
    ("dog", "Hund"),
    ("family", "Familie"),
    ("tree", "Baum"),
    ("road", "Straße"),
    ("music", "Musik")
]

# File to store subscribed users
USER_FILE = "users.json"


# Load existing users from file
def load_users():
    try:
        with open(USER_FILE, "r") as file:
            return set(json.load(file))  # Convert list to set
    except (FileNotFoundError, json.JSONDecodeError):
        return set()  # If file not found, return empty set


def save_users():
    with open(USER_FILE, "w") as file:
        json.dump(list(subscribed_users), file)  # Convert set to list


# Initialize the set of users
subscribed_users = load_users()

# Dictionary to store active quiz words for each user
active_quiz = {}  # {chat_id: (question, correct_answer, language)}


def log_received_message(update):
    """Log every received message."""
    chat_id = update.message.chat.id
    user_name = update.message.from_user.full_name
    user_message = update.message.text
    logger.info(f"Received from {user_name} (ID: {chat_id}): {user_message}")


def log_sent_message(chat_id, text):
    """Log every sent message."""
    logger.info(f"Sent to (ID: {chat_id}): {text}")


async def quiz(update, context):
    """Handle the /quiz command and send a quiz to the user."""
    log_received_message(update)
    await send_quiz(update.message.chat.id)

async def send_quiz(chat_id, is_scheduled=False):
    """Send a random English or German word for translation."""
    eng, ger = random.choice(word_list)  # Pick a random word pair

    # Randomly decide whether to ask for the English or German translation
    if random.choice([True, False]):
        question, answer, lang = eng, ger, "English"  # Ask for German
    else:
        question, answer, lang = ger, eng, "German"  # Ask for English

    message = f"🔍 Translate this word from {lang}:\n➡️ *{question}*"

    try:
        bot = Application.builder().token(TOKEN).build().bot
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

        # Store the active quiz word for checking later
        active_quiz[chat_id] = (question, answer, lang)

        log_prefix = "[Scheduled]" if is_scheduled else "[Manual /quiz]"
        log_sent_message(chat_id, f"{log_prefix} {message}")

    except Exception as e:
        logger.error(f"Failed to send quiz to {chat_id}: {e}")

async def check_answer(update, context):
    """Check if the user's answer is correct."""
    log_received_message(update)

    chat_id = update.message.chat.id
    user_response = update.message.text.strip()

    if chat_id in active_quiz:
        question, correct_answer, lang = active_quiz[chat_id]

        if user_response.lower() == correct_answer.lower():
            response = "✅ Correct! Well done! 🎉"
        else:
            response = f"❌ Wrong! The correct answer is: *{correct_answer}*"

        await update.message.reply_text(response, parse_mode="Markdown")
        log_sent_message(chat_id, response)

        # Remove the question after answering
        del active_quiz[chat_id]
    else:
        response = "I wasn't asking a word. Type /quiz to start!"
        await update.message.reply_text(response)
        log_sent_message(chat_id, response)


async def start(update, context):
    """Send a welcome message."""
    log_received_message(update)

    response = "👋 Hello! Use /quiz to practice or /subscribe to receive daily words at 9 AM!"
    await update.message.reply_text(response)
    log_sent_message(update.message.chat.id, response)


async def subscribe(update, context):
    """Subscribe the user to daily messages."""
    log_received_message(update)

    chat_id = update.message.chat.id

    if chat_id not in subscribed_users:
        subscribed_users.add(chat_id)
        save_users()
        response = "✅ You are now subscribed to daily English-German words!"
    else:
        response = "🔹 You are already subscribed!"

    await update.message.reply_text(response)
    log_sent_message(chat_id, response)


async def unsubscribe(update, context):
    """Unsubscribe the user from daily messages."""
    log_received_message(update)

    chat_id = update.message.chat.id

    if chat_id in subscribed_users:
        subscribed_users.remove(chat_id)
        save_users()
        response = "❌ You have unsubscribed from daily words."
    else:
        response = "🔹 You are not subscribed."

    await update.message.reply_text(response)
    log_sent_message(chat_id, response)


async def send_daily_quiz():
    """Send a scheduled quiz to all subscribed users."""
    for user in subscribed_users:
        await send_quiz(user, is_scheduled=True)

async def debug(update, context):
    await send_daily_quiz()

# Schedule daily quiz at 9 AM
def schedule_quiz():
    """Run the scheduled quiz function asynchronously."""
    asyncio.run(send_daily_quiz())


schedule.every().day.at("09:00").do(schedule_quiz)


# Run the scheduler in a separate thread
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)


scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Setting up the bot with the new API
app = Application.builder().token(TOKEN).build()

# Add command handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(CommandHandler("subscribe", subscribe))
app.add_handler(CommandHandler("unsubscribe", unsubscribe))
app.add_handler(CommandHandler("debug", debug))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))

# Start the bot
logger.info("Bot is running...")
app.run_polling()
