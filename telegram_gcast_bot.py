"""
Telegram Hybrid GCast Bot v3.3 — Auto Keyword Search & Multi-Userbot System
==========================================================================
"""

import telebot
from pyrogram import Client
import json
import os
import asyncio
import threading
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────
# KONFIGURASI UTAMA
# ──────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8665011485:AAEbubrLFGrG6ErO06FHhXPKwRtGA1lm7cM"   # Token Bot Utama Anda
OWNER_ID = 7240245056                                          # ID Telegram Anda (Owner)
DB_FILE = "userbot_db.json"                                    # Database penyimpanan multi-user
# ──────────────────────────────────────────────────────────────────────

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Helper state untuk alur login interaktif
user_login_state = {}

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {"users": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Handlers Bot Utama ────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or "Tanpa Username"
    first_name = message.from_user.first_name

    if uid != str(OWNER_ID):
        notif_text = (f"🔔 <b>Pengguna Baru Memulai Bot!</b>\n\n"
                      f"👤 Nama: {first_name}\n"
                      f"🆔 ID: <code>{uid}</code>\n"
                      f"🌐 Username: @{username}\n"
                      f"📅 Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            bot.send_message(OWNER_ID, notif_text)
        except:
            pass

    welcome_text = (f"👋 Halo <b>{first_name}</b>!\n\n"
                    f"Ini adalah Bot GCast Massal otomatis mencari grup berdasarkan kata kunci.\n"
                    f"Aman, mandiri, dan tidak perlu mengundang bot ke dalam grup.\n\n"
                    f"📋 <b>Perintah Tersedia:</b>\n"
                    f"/register - Daftarkan akun Anda ke sistem\n"
                    f"/gcastotomatis - Cari grup & sebar iklan instan")
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["register"])
def cmd_register(message):
    uid = message.from_user.id
    user_login_state[uid] = {"step": "INPUT_API_ID"}
    bot.reply_to(message, "⚙️ Mulai Pendaftaran.\n\nSilakan masukkan <b>API ID</b> Anda:")


@bot.message_handler(func=lambda msg: user_login_state.get(msg.from_user.id) is not None)
def handle_login_flow(message):
    uid = message.from_user.id
    state = user_login_state[uid]
    step = state["step"]

    if step == "INPUT_API_ID":
        if not message.text.isdigit():
            return bot.reply_to(message, "❌ API ID harus berupa angka!")
        state["api_id"] = int(message.text)
        state["step"] = "INPUT_API_HASH"
        bot.reply_to(message, "✅ API ID disimpan. Masukkan <b>API HASH</b> Anda:")

    elif step == "INPUT_API_HASH":
        state["api_hash"] = message.text.strip()
        state["step"] = "INPUT_PHONE"
        bot.reply_to(message, "✅ API HASH disimpan. Masukkan <b>Nomor HP Akun Telegram</b> (+62...):")

    elif step == "INPUT_PHONE":
        phone = message.text.strip().replace(" ", "")
        state["phone"] = phone
        bot.reply_to(message, "⏳ Sedang mengirim kode OTP dari Telegram...")
        
        loop = asyncio.new_event_loop()
        t = threading.Thread(target=run_async_login, args=(loop, uid, state))
        t.start()


def run_async_login(loop, uid, state):
    loop.run_until_complete(async_auth_telegram(uid, state))

async def async_auth_telegram(uid, state):
    session_name = f"sessions/user_{uid}"
    os.makedirs("sessions", exist_ok=True)
    
    client = Client(
        session_name, 
        api_id=state["api_id"], 
        api_hash=state["api_hash"], 
        phone_number=state["phone"],
        device_model="PC 64bit",
        system_version="Windows 11"
    )
    state["client"] = client

    try:
        await client.connect()
        code_hash = await client.send_code(state["phone"])
        state["code_hash"] = code_hash
        state["step"] = "INPUT_OTP"
        bot.send_message(uid, "📩 <b>Kode OTP Terkirim!</b>\nMasukkan kode verifikasi Anda (Kasih spasi di tengah angka, contoh: <code>1 2 3 4 5</code>)")
    except Exception as e:
        bot.send_message(uid, f"❌ Gagal mengirim OTP: {str(e)}")
        user_login_state.pop(uid, None)


@bot.message_handler(func=lambda msg: user_login_state.get(msg.from_user.id, {}).get("step") == "INPUT_OTP")
def handle_otp_input(message):
    uid = message.from_user.id
    state = user_login_state[uid]
    otp_code = message.text.strip().replace(" ", "")

    bot.reply_to(message, "⚡ Memverifikasi kode OTP...")
    
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_async_verify, args=(loop, uid, state, otp_code))
    t.start()

def run_async_verify(loop, uid, state, otp_code):
    loop.run_until_complete(async_verify_otp(uid, state, otp_code))

async def async_verify_otp(uid, state, otp_code):
    client = state["client"]
    try:
        await client.sign_in(state["phone"], state["code_hash"].phone_code_hash, otp_code)
        me = await client.get_me()
        
        db = load_db()
        db["users"][str(uid)] = {
            "api_id": state["api_id"],
            "api_hash": state["api_hash"],
            "phone": state["phone"],
            "name": me.first_name,
            "username": me.username or ""
        }
        save_db(db)
        
        bot.send_message(uid, f"🎉 <b>Pendaftaran Berhasil!</b>\n\nAkun Anda: <b>{me.first_name}</b> telah aktif.\nGunakan perintah /gcastotomatis.")
        bot.send_message(OWNER_ID, f"🚀 <b>Userbot Baru Aktif!</b>\n\n👤 User: {me.first_name}\n🆔 ID: <code>{uid}</code>")
        
    except Exception as e:
        bot.send_message(uid, f"❌ Gagal Verifikasi OTP: {str(e)}")
    finally:
        await client.disconnect()
        user_login_state.pop(uid, None)


# ── Fitur Pencarian & Broadcast Otomatis Global ───────────────────────

@bot.message_handler(commands=["gcastotomatis"])
def cmd_gcast_otomatis(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    if uid not in db["users"]:
        return bot.reply_to(message, "❌ Silakan ketik /register terlebih dahulu.")
        
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return bot.reply_to(message, "❌ <b>Cara Pakai:</b>\n<code>/gcastotomatis [KataKunci] [Pesan Iklan]</code>\n\n<b>Contoh:</b>\n<code>/gcastotomatis parlay Info bola malam ini bosku jamin jp!</code>")
        
    keyword = parts[1].strip()
    pesan_iklan = parts[2].strip()
    
    bot.reply_to(message, f"📡 <b>Membuka Koneksi...</b>\nUserbot akan otomatis mencari 10 grup publik global dengan kata kunci <b>'{keyword}'</b>, bergabung, dan mengirimkan pesan iklan Anda.")
    
    user_data = db["users"][uid]
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_async_search_broadcast, args=(loop, uid, user_data, keyword, pesan_iklan))
    t.start()

def run_async_search_broadcast(loop, uid, user_data, keyword, pesan):
    loop.run_until_complete(async_userbot_search_broadcast(uid, user_data, keyword, pesan))

async def async_userbot_search_broadcast(uid, user_data, keyword, pesan):
    session_name = f"sessions/user_{uid}"
    client = Client(session_name, api_id=user_data["api_id"], api_hash=user_data["api_hash"])
    
    try:
        await client.connect()
        sukses = 0
        
        # 1. Otomatis mencari grup publik global berdasarkan keyword di Telegram server
        search_results = await client.search_chats(keyword, limit=10)
        
        for chat in search_results:
            # Pastikan tipe obrolan adalah grup publik/supergroup
            if chat.type in ["group", "supergroup"] and chat.username:
                try:
                    # 2. Otomatis join ke dalam grup tersebut tanpa perlu diundang
                    await client.join_chat(chat.username)
                    
                    # 3. Otomatis kirim pesan iklan
                    await client.send_message(chat.id, pesan)
                    sukses += 1
                    
                    # Jeda waktu aman 8 detik demi menghindari limit/ban
                    await asyncio.sleep(8)
                except Exception:
                    continue
                
        bot.send_message(uid, f"✅ <b>Gcast Otomatis Selesai!</b>\nBerhasil menemukan grup baru, masuk, dan menyebarkan iklan ke <b>{sukses} grup</b> berbasis kata kunci: <i>{keyword}</i>.")
    except Exception as e:
        bot.send_message(uid, f"❌ Kendala operasional userbot: {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("🤖 Bot System Hybrid Engine v3.3 Active...")
    bot.infinity_polling()
