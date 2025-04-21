import telebot
import time 
import os
import time 
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from threading import Thread 
from flask import Flask 

# Replace with your credentials
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6897739611

MONGO_URI = os.getenv("DB_URL")
DB_NAME = "telegram_bot"
USERS_COLLECTION = "users"
BLOCKED_COLLECTION = "blocked_users"

bot = telebot.TeleBot(BOT_TOKEN)

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db[USERS_COLLECTION]
blocked_collection = db[BLOCKED_COLLECTION]
MESSAGE_MAPPING_COLLECTION = "message_mappings"
message_mapping_collection = db[MESSAGE_MAPPING_COLLECTION]


app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run_http_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_http_server)
    t.start()

# Dictionary to track forwarded messages
message_mapping = {}

def save_user(user_id, username):
    """Saves user ID and username to MongoDB if not blocked."""
    if not users_collection.find_one({"user_id": user_id}) and not is_user_blocked(user_id):
        users_collection.insert_one({"user_id": user_id, "username": username})
        print(f"New user saved: {user_id}")

def is_user_blocked(user_id):
    """Checks if the user is blocked."""
    return blocked_collection.find_one({"user_id": user_id}) is not None

@bot.message_handler(commands=["start"])
def send_welcome(message):
    """Handles the /start command."""
    user_id = message.chat.id
    username = message.from_user.username or "No username"

    if is_user_blocked(user_id):
        bot.send_message(user_id, "🚫 You are blocked by the admin.")
        return

    save_user(user_id, username)

    welcome_text = (
        "👋 *Welcome to the Bot!* 🎉\n\n"
        "🚀 This bot allows you to send messages to the admin even if you are restricted.\n"
        "💬 Just send your message here, and it will be forwarded!\n\n"
        "🔹 *Developer:* [Ｂｏｔｐｌａｙｓ](https://t.me/botplays90)\n"
        "🔹 *Join:* [Hyponet](https://t.me/join_hyponet)\n"
    )

    # Create inline buttons
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/botplays90"),
        InlineKeyboardButton("📢 Join Channel", url="https://t.me/join_hyponet")
    )

    bot.send_message(user_id, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.chat.id != ADMIN_ID)
def forward_to_admin(message):
    """Forwards user messages to the admin and stores mapping in MongoDB."""
    user_id = message.chat.id

    if is_user_blocked(user_id):
        bot.send_message(user_id, "🚫 You are blocked by the admin.")
        return

    forwarded_message = bot.forward_message(ADMIN_ID, user_id, message.message_id)

    # Store mapping in MongoDB
    message_mapping_collection.insert_one({
        "forwarded_message_id": forwarded_message.message_id,
        "user_id": user_id
    })



@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
def reply_to_user(message):
    """Replies to the original user when the admin replies to a forwarded message."""
    original_message_id = message.reply_to_message.message_id

    # Fetch user_id from MongoDB
    mapping = message_mapping_collection.find_one({"forwarded_message_id": original_message_id})

    if mapping:
        user_id = mapping["user_id"]
        bot.send_message(user_id, f"💬 *Admin:* {message.text}", parse_mode="Markdown")
        bot.send_message(ADMIN_ID, "✅ Message sent successfully!")
    else:
        bot.send_message(ADMIN_ID, "⚠️ Error: Could not find the original sender.")




def send_media_to_admin(message):
    """Handles all media types and forwards them to the admin."""
    user_id = message.chat.id

    if is_user_blocked(user_id):
        bot.send_message(user_id, "🚫 You are blocked by the admin.")
        return

    caption_text = f"📩 *Message from:* `{user_id}`\n"
    media_type = message.content_type
    file_id = None
    forwarded_message = None

    if media_type == "photo":
        file_id = message.photo[-1].file_id
        forwarded_message = bot.send_photo(ADMIN_ID, file_id, caption=caption_text)
    elif media_type == "video":
        file_id = message.video.file_id
        forwarded_message = bot.send_video(ADMIN_ID, file_id, caption=caption_text)
    elif media_type == "audio":
        file_id = message.audio.file_id
        forwarded_message = bot.send_audio(ADMIN_ID, file_id, caption=caption_text)
    elif media_type == "document":
        file_id = message.document.file_id
        forwarded_message = bot.send_document(ADMIN_ID, file_id, caption=caption_text)
    elif media_type == "sticker":
        file_id = message.sticker.file_id
        forwarded_message = bot.send_sticker(ADMIN_ID, file_id)
    elif media_type == "voice":
        file_id = message.voice.file_id
        forwarded_message = bot.send_voice(ADMIN_ID, file_id)

    if forwarded_message:
        message_mapping_collection.insert_one({
            "forwarded_message_id": forwarded_message.message_id,
            "user_id": user_id,
            "message_type": media_type,
            "file_id": file_id
        })

@bot.message_handler(content_types=['photo', 'video', 'audio', 'document', 'sticker', 'voice'])
def handle_media_message(message):
    send_media_to_admin(message)  # Calls our function for media






@bot.message_handler(commands=["block"])
def block_user(message):
    """Blocks a user by user ID."""
    if message.chat.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if not is_user_blocked(user_id):
                blocked_collection.insert_one({"user_id": user_id})
                bot.send_message(user_id, "🚫 You are blocked by the admin.")
                bot.send_message(ADMIN_ID, f"✅ User *{user_id}* has been blocked.", parse_mode="Markdown")
            else:
                bot.send_message(ADMIN_ID, "⚠️ This user is already blocked.")
        except (IndexError, ValueError):
            bot.send_message(ADMIN_ID, "⚠️ Usage: `/block user_id`", parse_mode="Markdown")

@bot.message_handler(commands=["unblock"])
def unblock_user(message):
    """Unblocks a user by user ID."""
    if message.chat.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if is_user_blocked(user_id):
                blocked_collection.delete_one({"user_id": user_id})
                bot.send_message(user_id, "✅ You are unblocked by the admin. You can message again.")
                bot.send_message(ADMIN_ID, f"✅ User *{user_id}* has been unblocked.", parse_mode="Markdown")
            else:
                bot.send_message(ADMIN_ID, "⚠️ This user is not blocked.")
        except (IndexError, ValueError):
            bot.send_message(ADMIN_ID, "⚠️ Usage: `/unblock user_id`", parse_mode="Markdown")
@bot.message_handler(commands=["users"])
def list_users(message):
    """Lists all saved users with numbering."""
    if message.chat.id == ADMIN_ID:
        users = list(users_collection.find({}, {"user_id": 1, "_id": 0}))  # Fetch user IDs only
        if users:
            user_list = "\n".join([f"{i+1}. `{user['user_id']}`" for i, user in enumerate(users)])
            bot.send_message(ADMIN_ID, f"👥 *Saved Users:*\n{user_list}", parse_mode="Markdown")
        else:
            bot.send_message(ADMIN_ID, "⚠️ No users found in the database.")







@bot.message_handler(commands=["broadcast"])
def broadcast_message(message):
    """Broadcasts a message to all users (only for admin)."""
    if message.chat.id == ADMIN_ID:
        try:
            broadcast_text = message.text.split(" ", 1)[1]
            users = users_collection.find()
            for user in users:
                try:
                    bot.send_message(user["user_id"], f"📢 *Broadcast Message:*\n\n{broadcast_text}", parse_mode="Markdown")
                except:
                    pass  # Ignore users who have blocked the bot
            bot.send_message(ADMIN_ID, "✅ Broadcast sent successfully!")
        except IndexError:
            bot.send_message(ADMIN_ID, "⚠️ Usage: /broadcast Your message here.")

keep_alive()

bot.infinity_polling()
