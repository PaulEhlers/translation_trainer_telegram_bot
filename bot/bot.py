import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import ReactionTypeEmoji
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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

USER_FILE = "users.json"
WORDS_FILE = "words.json"

AMOUNT_WORDS_PER_QUIZ = 5


def load_words():
    try:
        with open(WORDS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Datei {WORDS_FILE} nicht gefunden! Stelle sicher, dass sie existiert.")
        return []
    except json.JSONDecodeError:
        logger.error(f"Fehler beim Lesen von {WORDS_FILE}. Stelle sicher, dass die Datei gültiges JSON enthält.")
        return []


word_list = load_words()


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
    selected_words = random.sample(word_list, AMOUNT_WORDS_PER_QUIZ)
    ask_in_english = random.choice([True, False])

    message = f"🔍 Translate these 5 words **into {'German' if ask_in_english else 'English'}**:\n\n"
    words = []

    for idx, (eng, ger) in enumerate(selected_words, start=1):
        question = eng if ask_in_english else ger  # Ask in one language
        answer = ger if ask_in_english else eng  # Expect answer in the other

        words.append((question, answer))  # Store question-answer pair
        message += f"{idx}. {question}\n"

    try:
        bot = Application.builder().token(TOKEN).build().bot
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

        log_prefix = "[Scheduled]" if is_scheduled else "[Manual /quiz]"
        log_sent_message(chat_id, f"{log_prefix} {message}")

    except Exception as e:
        logger.error(f"Failed to send quiz to {chat_id}: {e}")

    active_quiz[chat_id] = {"words": words, "answers_received": []}
    log_sent_message(chat_id, message)


async def check_answer(update, context):
    """Check if the user's answer is correct."""
    log_received_message(update)

    chat_id = update.message.chat.id
    message_id = update.message.message_id
    user_response = update.message.text.strip()

    if chat_id not in active_quiz:
        await update.message.reply_text("I wasn't asking a word. Type /quiz to start!", parse_mode="Markdown")
        return

    quiz_data = active_quiz[chat_id]
    words = quiz_data["words"]
    answers_received = quiz_data["answers_received"]

    correct_answer = words[len(answers_received)][1]  # Get expected answer for current position
    is_correct = user_response.lower() == correct_answer.lower()

    # React with an emoji instead of sending a message
    try:
        reaction = [ReactionTypeEmoji('👍' if is_correct else '👎')]
        await context.bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=reaction
        )
    except Exception as e:
        logger.error(f"Failed to react with emoji for user {chat_id}: {e}")

    # Store answer status
    answers_received.append(is_correct)

    # If 5 answers received, summarize results
    if len(answers_received) == 5:
        correct_count = sum(answers_received)
        summary = f"📊 **Quiz Results:** {correct_count}/5 correct!\n\n"

        for idx, (word, answer) in enumerate(words, start=1):
            status = "✅" if answers_received[idx - 1] else "❌"
            summary += f"{idx}. {word} → {answer} {status}\n"

        await update.message.reply_text(summary, parse_mode="Markdown")
        log_sent_message(chat_id, summary)

        del active_quiz[chat_id]  # Remove quiz after summary


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
