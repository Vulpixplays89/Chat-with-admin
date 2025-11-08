import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
from pyrogram.enums import ParseMode
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent, CallbackQuery
import uuid

from threading import Thread
from flask import Flask

# ENV Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = 26222466
API_HASH = "9f70e2ce80e3676b56265d4510561aef"
ADMIN_ID = 6897739611

MONGO_URI = os.getenv("DB_URL")
DB_NAME = "telegram_bot"

# Pyrogram client
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db["users"]
blocked_collection = db["blocked_users"]
message_mapping_collection = db["message_mappings"]

selected_users = {}



# Flask app for keep-alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "I am alive!"

def run_http_server():
    flask_app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run_http_server).start()

# Utils
def save_user(user_id, username):
    if not users_collection.find_one({"user_id": user_id}) and not is_user_blocked(user_id):
        users_collection.insert_one({"user_id": user_id, "username": username or "No username"})

def is_user_blocked(user_id):
    return blocked_collection.find_one({"user_id": user_id}) is not None

# Handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"

    if is_user_blocked(user_id):
        await message.reply("🚫 You are blocked by the admin.")
        return

    save_user(user_id, username)

    welcome_text = (
        "👋 <b>Welcome to the Bot!</b> 🎉\n\n"
        "🚀 This bot allows you to send messages to the admin even if you are restricted.\n"
        "💬 Just send your message here, and it will be forwarded!\n\n"
        "(Not Like Your Ordinary Live Gram Bot 🗿)\n\n"
        "🔹 <b>Developer:</b> <a href='https://t.me/botplays90'>Ｂｏｔｐｌａｙｓ</a>\n"
        "🔹 <b>Join:</b> <a href='https://t.me/hyponet_remastered'>Hyponet</a>"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/botplays90")],
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/join_hyponet")]
    ])

    await message.reply(welcome_text, reply_markup=markup, parse_mode=ParseMode.HTML)

@app.on_message(filters.private & ~filters.user(ADMIN_ID))
async def forward_to_admin(client, message: Message):
    user_id = message.from_user.id

    if is_user_blocked(user_id):
        await message.reply("🚫 You are blocked by the admin.")
        return

    try:
        # ✅ Forward as-is (shows user info like "from Vulpix")
        forwarded = await message.forward(ADMIN_ID)

        # ✅ Store mapping in DB
        message_mapping_collection.insert_one({
            "forwarded_message_id": forwarded.id,
            "user_id": user_id
        })

    except Exception as e:
        await message.reply("❌ Failed to forward your message. Please try again later.")
        print(f"Forward error: {e}")



@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.reply)
async def reply_to_user(client, message: Message):
    try:
        original_msg_id = message.reply_to_message.id

        mapping = message_mapping_collection.find_one({
            "forwarded_message_id": original_msg_id
        })

        if mapping:
            user_id = mapping["user_id"]
            await message.copy(user_id)
            await message.reply("✅ Message sent.")
        else:
            await message.reply("⚠️ Could not find user ID in the original message.")

    except Exception as e:
        await message.reply("❌ Error while sending the message.")
        print(f"Reply error: {e}")


@app.on_message(filters.private & filters.media & ~filters.user(ADMIN_ID))
async def forward_media(client, message: Message):
    user_id = message.from_user.id
    if is_user_blocked(user_id):
        await message.reply("🚫 You are blocked by the admin.")
        return

    try:
        caption = f"📩 <b>Message from:</b> <code>{user_id}</code>"
        sent = await message.copy(ADMIN_ID, caption=caption, parse_mode=ParseMode.HTML)
        message_mapping_collection.insert_one({
            "forwarded_message_id": sent.message_id,
            "user_id": user_id,
            "file_id": message.media.file_id
        })
    except Exception as e:
        await message.reply("❌ Failed to forward your media.")

@app.on_message(filters.command("block") & filters.user(ADMIN_ID))
async def block_user(client, message: Message):
    try:
        user_id = int(message.text.split()[1])
        if not is_user_blocked(user_id):
            blocked_collection.insert_one({"user_id": user_id})
            await client.send_message(user_id, "🚫 You are blocked by the admin.")
            await message.reply(f"✅ User <code>{user_id}</code> has been blocked.", parse_mode=ParseMode.HTML)
        else:
            await message.reply("⚠️ This user is already blocked.")
    except Exception:
        await message.reply("⚠️ Usage: /block user_id")

@app.on_message(filters.command("unblock") & filters.user(ADMIN_ID))
async def unblock_user(client, message: Message):
    try:
        user_id = int(message.text.split()[1])
        if is_user_blocked(user_id):
            blocked_collection.delete_one({"user_id": user_id})
            await client.send_message(user_id, "✅ You are unblocked by the admin. You can message again.")
            await message.reply(f"✅ User <code>{user_id}</code> has been unblocked.", parse_mode=ParseMode.HTML)
        else:
            await message.reply("⚠️ This user is not blocked.")
    except Exception:
        await message.reply("⚠️ Usage: /unblock user_id")

@app.on_message(filters.command("users") & filters.user(ADMIN_ID))
async def list_users(client, message: Message):
    users = list(users_collection.find({}, {"user_id": 1, "_id": 0}))
    if users:
        text = "\n".join([f"{i+1}. <code>{u['user_id']}</code>" for i, u in enumerate(users)])
        await message.reply(f"👥 <b>Saved Users:</b>\n{text}", parse_mode=ParseMode.HTML)
    else:
        await message.reply("⚠️ No users found in the database.")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast(client, message: Message):
    try:
        text = message.text.split(" ", 1)[1]
        users = users_collection.find()
        count = 0
        for u in users:
            try:
                await client.send_message(u["user_id"], f"📢 <b>Broadcast Message:</b>\n\n{text}", parse_mode=ParseMode.HTML)
                count += 1
            except:
                continue
        await message.reply(f"✅ Broadcast sent to {count} users.")
    except IndexError:
        await message.reply("⚠️ Usage: /broadcast Your message here.")

@app.on_inline_query()
async def inline_query_handler(client, inline_query):
    if inline_query.from_user.id != ADMIN_ID:
        return

    query = inline_query.query.strip().lower()
    results = []

    if not query:
        return await inline_query.answer(results=[], cache_time=1)

    users = users_collection.find({
        "$or": [
            {"username": {"$regex": query, "$options": "i"}},
            {"user_id": {"$regex": query if query.isdigit() else "000000000"}}
        ]
    }).limit(20)

    for user in users:
        uid = user['user_id']
        uname = user.get("username", "No username")
        results.append(
            InlineQueryResultArticle(
                title=f"{uname} ({uid})",
                input_message_content=InputTextMessageContent(
                    message_text=f"User selected: <code>{uid}</code>",
                    parse_mode=ParseMode.HTML
                ),
                description=f"Click to message {uname}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Send Message", callback_data=f"sendmsg_{uid}")]
                ]),
                id=str(uuid.uuid4())
            )
        )

    await inline_query.answer(results, cache_time=0)

@app.on_callback_query(filters.regex("^sendmsg_"))
async def handle_sendmsg_callback(client, callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    selected_users[callback_query.from_user.id] = user_id

    # Send instruction message to admin
    await client.send_message(
        chat_id=callback_query.from_user.id,
        text=f"✉️ Now send the message you want to deliver to <code>{user_id}</code>",
        parse_mode=ParseMode.HTML
    )

    await callback_query.answer("User selected ✅")


@app.on_message(filters.private & filters.user(ADMIN_ID))
async def admin_send_to_selected_user(client, message: Message):
    if message.reply_to_message:  # keep existing reply logic
        return

    user_id = selected_users.get(message.from_user.id)
    if user_id:
        try:
            await message.copy(user_id)
            await message.reply(f"✅ Message sent to <code>{user_id}</code>.", parse_mode=ParseMode.HTML)
            del selected_users[message.from_user.id]
        except Exception as e:
            await message.reply("❌ Failed to send message.")
            print(e)


# Run
keep_alive()

if __name__ == "__main__":
    app.run()
