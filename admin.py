import telebot
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
        "🔹 *Developer:* [@botplays90](https://t.me/botplays90)\n"
        "🔹 *Join:* [Hyponet](https://t.me/join_hyponet)\n"
    )

    # Create inline buttons
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/botplays90"),
        InlineKeyboardButton("📢 Join Channel", url="https://t.me/join_hyponet")
    )

    bot.send_message(user_id, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: not (message.text and message.text.startswith("/")) and message.chat.id != ADMIN_ID, 
                     content_types=['text', 'photo', 'audio', 'voice', 'video', 'document', 'sticker'])
def forward_user_message_to_admin(message):
    """Forwards user messages and files to the admin, but ignores commands."""
    user_id = message.chat.id  # User who sent the message

    if is_user_blocked(user_id):
        bot.send_message(user_id, "🚫 You are blocked by the admin.")
        return

    try:
        # Forward message or media to admin
        forwarded_message = bot.forward_message(ADMIN_ID, user_id, message.message_id)

        # Notify admin with a reply message
        bot.send_message(
            ADMIN_ID,
            f"📩 *New message from user:* `{user_id}`\n"
            "Reply by selecting this message and typing your response.",
            parse_mode="Markdown",
            reply_to_message_id=forwarded_message.message_id
        )
    except Exception as e:
        print(f"⚠️ Error forwarding message from {user_id}: {e}")
        bot.send_message(ADMIN_ID, f"⚠️ Error forwarding message from {user_id}: {e}")



@bot.message_handler(commands=["send"])
def ask_for_media(message):
    """Handles /send <userid> command and waits for the admin to send a file."""
    if message.chat.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            db.pending_requests.update_one(
                {"admin_id": ADMIN_ID},
                {"$set": {"user_id": user_id}},
                upsert=True
            )
            bot.send_message(ADMIN_ID, f"📩 Send the file/message you want to send to *{user_id}*.", parse_mode="Markdown")

        except (IndexError, ValueError):
            bot.send_message(ADMIN_ID, "⚠️ Usage: `/send user_id`", parse_mode="Markdown")

# Add send_to_user() before media handlers
def send_to_user(message, caption, file_id=None, file_type=None):
    """Sends a message or media to the user stored in MongoDB."""
    pending_request = db.pending_requests.find_one({"admin_id": ADMIN_ID})

    if not pending_request:
        bot.send_message(ADMIN_ID, "⚠️ No active /send request. Use `/send user_id` first.")
        return

    user_id = pending_request["user_id"]
    db.pending_requests.delete_one({"admin_id": ADMIN_ID})  # Clear request

    try:
        if file_type is None:  # Text message
            bot.send_message(user_id, f"{caption} {message.text}", parse_mode="Markdown")
        elif file_type == "photo":
            bot.send_photo(user_id, file_id, caption=message.caption or caption)
        elif file_type == "audio":
            bot.send_audio(user_id, file_id, caption=message.caption or caption)
        elif file_type == "voice":
            bot.send_voice(user_id, file_id, caption=message.caption or caption)
        elif file_type == "video":
            bot.send_video(user_id, file_id, caption=message.caption or caption)
        elif file_type == "document":
            bot.send_document(user_id, file_id, caption=message.caption or caption)
        elif file_type == "sticker":
            bot.send_sticker(user_id, file_id)

        bot.send_message(ADMIN_ID, f"✅ Message/file successfully sent to {user_id}!")

    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ Error sending message to {user_id}: {e}")

# ✅ Now, add media handlers below this function
@bot.message_handler(content_types=['text'])
def send_text_to_user(message):
    send_to_user(message, "💬 *Admin:*")

@bot.message_handler(content_types=['photo'])
def send_photo_to_user(message):
    send_to_user(message, "📷 Sent by Admin", message.photo[-1].file_id, "photo")

@bot.message_handler(content_types=['audio'])
def send_audio_to_user(message):
    send_to_user(message, "🎵 Sent by Admin", message.audio.file_id, "audio")

@bot.message_handler(content_types=['voice'])
def send_voice_to_user(message):
    send_to_user(message, "🔊 Sent by Admin", message.voice.file_id, "voice")

@bot.message_handler(content_types=['video'])
def send_video_to_user(message):
    send_to_user(message, "📹 Sent by Admin", message.video.file_id, "video")

@bot.message_handler(content_types=['document'])
def send_document_to_user(message):
    send_to_user(message, "📄 Sent by Admin", message.document.file_id, "document")

@bot.message_handler(content_types=['sticker'])
def send_sticker_to_user(message):
    send_to_user(message, None, message.sticker.file_id, "sticker")



@bot.message_handler(content_types=["any"])
def send_media_to_user(message):
    """Sends the received file, image, or message to the user."""
    # Retrieve and delete pending request from MongoDB
    pending_request = db.pending_requests.find_one({"admin_id": ADMIN_ID})

    if not pending_request:
        bot.send_message(ADMIN_ID, "⚠️ No active /send request. Use `/send user_id` first.")
        return

    user_id = pending_request["user_id"]

    # Delete request to prevent reuse
    db.pending_requests.delete_one({"admin_id": ADMIN_ID})

    print(f"✅ Sending media to user {user_id}")  # Debugging Line

    try:
        if message.text:
            bot.send_message(user_id, f"💬 *Admin:* {message.text}", parse_mode="Markdown")
        elif message.photo:
            bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption or "📷 Sent by Admin")
        elif message.audio:
            bot.send_audio(user_id, message.audio.file_id, caption=message.caption or "🎵 Sent by Admin")
        elif message.voice:
            bot.send_voice(user_id, message.voice.file_id, caption=message.caption or "🔊 Sent by Admin")
        elif message.video:
            bot.send_video(user_id, message.video.file_id, caption=message.caption or "📹 Sent by Admin")
        elif message.document:
            bot.send_document(user_id, message.document.file_id, caption=message.caption or "📄 Sent by Admin")
        elif message.sticker:
            bot.send_sticker(user_id, message.sticker.file_id)
        else:
            bot.send_message(ADMIN_ID, "⚠️ Unsupported message type.")

        bot.send_message(ADMIN_ID, f"✅ Message/file successfully sent to {user_id}!")

    except Exception as e:
        print(f"⚠️ Error sending message to {user_id}: {e}")  # Debugging
        bot.send_message(ADMIN_ID, f"⚠️ Error sending message to {user_id}: {e}")


@bot.message_handler(commands=["block"])
def block_user(message):
    """Blocks a user by user ID."""
    if message.chat.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if is_user_blocked(user_id):
                bot.send_message(ADMIN_ID, "⚠️ This user is already blocked.")
                return
            
            blocked_collection.insert_one({"user_id": user_id})
            bot.send_message(ADMIN_ID, f"✅ User *{user_id}* has been blocked.", parse_mode="Markdown")

            # Try notifying the user
            try:
                bot.send_message(user_id, "🚫 You are blocked by the admin.")
            except:
                pass  # Ignore if the user blocked the bot

        except (IndexError, ValueError):
            bot.send_message(ADMIN_ID, "⚠️ Usage: `/block user_id`", parse_mode="Markdown")


@bot.message_handler(commands=["unblock"])
def unblock_user(message):
    """Unblocks a user by user ID."""
    if message.chat.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if not is_user_blocked(user_id):
                bot.send_message(ADMIN_ID, "⚠️ This user is not blocked.")
                return
            
            blocked_collection.delete_one({"user_id": user_id})
            bot.send_message(ADMIN_ID, f"✅ User *{user_id}* has been unblocked.", parse_mode="Markdown")

            # Try notifying the user
            try:
                bot.send_message(user_id, "✅ You are unblocked by the admin. You can message again.")
            except:
                pass  # Ignore if the user blocked the bot

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
            success_count = 0
            failed_count = 0

            for user in users:
                try:
                    bot.send_message(user["user_id"], f"📢 *Broadcast Message:*\n\n{broadcast_text}", parse_mode="Markdown")
                    success_count += 1
                except Exception as e:
                    failed_count += 1  # Count failed messages

            bot.send_message(ADMIN_ID, f"✅ Broadcast sent to {success_count} users!\n❌ Failed: {failed_count}")

        except IndexError:
            bot.send_message(ADMIN_ID, "⚠️ Usage: /broadcast Your message here.")


@bot.message_handler(content_types=["photo", "video", "audio", "voice", "document", "sticker", "animation"])
def forward_media_to_admin(message):
    """Forwards any media sent by users to the admin."""
    if message.chat.id == ADMIN_ID:
        return  # Ignore admin's media

    try:
        forwarded_message = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        bot.send_message(ADMIN_ID, f"📩 *New Media from* `{message.chat.id}`", parse_mode="Markdown",
                         reply_to_message_id=forwarded_message.message_id)
    except Exception as e:
        print(f"⚠️ Failed to forward media from {message.chat.id}: {e}")

@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
def reply_to_user_media(message):
    """Allows the admin to reply to a forwarded media message."""
    original_message_id = message.reply_to_message.message_id
    user_id = message.reply_to_message.forward_from.id if message.reply_to_message.forward_from else None

    if not user_id:
        bot.send_message(ADMIN_ID, "⚠️ Cannot detect the original sender.")
        return

    bot.send_message(user_id, f"💬 *Admin:* {message.text}", parse_mode="Markdown")
    bot.send_message(ADMIN_ID, "✅ Reply sent to the user!")




@bot.message_handler(func=lambda message: message.chat.id != ADMIN_ID)
def forward_to_admin(message):
    """Forwards user messages to the admin and stores mapping in MongoDB."""
    user_id = message.chat.id

    if is_user_blocked(user_id):
        bot.send_message(user_id, "🚫 You are blocked by the admin.")
        return

    forwarded_message = bot.forward_message(ADMIN_ID, user_id, message.message_id)
    
    # Store mapping in MongoDB
    db.message_mapping.insert_one({"forwarded_message_id": forwarded_message.message_id, "user_id": user_id})


@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
def reply_to_user(message):
    """Replies to the original user when the admin replies to a forwarded message."""
    original_message_id = message.reply_to_message.message_id

    mapping = db.message_mapping.find_one({"forwarded_message_id": original_message_id})
    
    if mapping:
        user_id = mapping["user_id"]
        bot.send_message(user_id, f"💬 *Admin:* {message.text}", parse_mode="Markdown")
        bot.send_message(ADMIN_ID, "✅ Message sent successfully!")
    else:
        bot.send_message(ADMIN_ID, "⚠️ Error: Could not find the original sender.")














keep_alive()

print("🚀 Bot is running...")
bot.infinity_polling(timeout=30, long_polling_timeout=10)

