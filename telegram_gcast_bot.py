"""
Telegram Hybrid GCast Bot v3.0 — Multi-Userbot & Owner Notification System
========================================================================
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
DB_FILE = "userbot_db.json"
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

    # Kirim Notifikasi ke Owner jika ada user baru yang memulai bot
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
                    f"Ini adalah Bot GCast Massal menggunakan akun Telegram Anda sendiri.\n"
                    f"Aman, mandiri, dan tidak perlu mengundang bot ke dalam grup.\n\n"
                    f"📋 <b>Langkah Pendaftaran:</b>\n"
                    f"1. Ambil API ID & API HASH Anda di: https://my.telegram.orgn"
                    f"2. Kirim perintah /register untuk memulai setup.")
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["register"])
def cmd_register(message):
    uid = message.from_user.id
    user_login_state[uid] = {"step": "INPUT_API_ID"}
    bot.reply_to(message, "⚙️ Mulai Pendaftaran.\n\nSilakan masukkan <b>API ID</b> Anda (Berupa Angka):")


@bot.message_handler(func=lambda msg: user_login_state.get(msg.from_user.id) is not None)
def handle_login_flow(message):
    uid = message.from_user.id
    state = user_login_state[uid]
    step = state["step"]

    if step == "INPUT_API_ID":
        if not message.text.isdigit():
            return bot.reply_to(message, "❌ API ID harus berupa angka! Silakan masukkan kembali:")
        state["api_id"] = int(message.text)
        state["step"] = "INPUT_API_HASH"
        bot.reply_to(message, "✅ API ID disimpan.\n\nSekarang masukkan <b>API HASH</b> Anda:")

    elif step == "INPUT_API_HASH":
        state["api_hash"] = message.text.strip()
        state["step"] = "INPUT_PHONE"
        bot.reply_to(message, "✅ API HASH disimpan.\n\nSekarang masukkan <b>Nomor HP Akun Telegram</b> Anda (Gunakan kode negara, contoh: <code>+62812345678</code>):")

    elif step == "INPUT_PHONE":
        phone = message.text.strip().replace(" ", "")
        state["phone"] = phone
        bot.reply_to(message, "⏳ Sedang mengirim kode OTP dari Telegram, mohon tunggu...")
        
        # Jalankan loop asinkronus Pyrogram di thread terpisah untuk verifikasi OTP
        loop = asyncio.new_event_loop()
        t = threading.Thread(target=run_async_login, args=(loop, uid, state))
        t.start()


# ── Pyrogram Core Asynchronous Auth ───────────────────────────────────

def run_async_login(loop, uid, state):
    loop.run_until_complete(async_auth_telegram(uid, state))

async def async_auth_telegram(uid, state):
    # Buat nama session file unik berdasarkan ID User
    session_name = f"sessions/user_{uid}"
    os.makedirs("sessions", exist_ok=True)
    
    client = Client(session_name, api_id=state["api_id"], api_hash=state["api_hash"], phone_number=state["phone"])
    state["client"] = client

    try:
        await client.connect()
        code_hash = await client.send_code(state["phone"])
        state["code_hash"] = code_hash
        state["step"] = "INPUT_OTP"
        
        bot.send_message(uid, "📩 <b>Kode OTP Terkirim!</b>\nSilakan periksa aplikasi Telegram resmi Anda, lalu masukkan kode verifikasi di sini.\n\nFormat input: Kasih spasi di tengah angka kode, contoh: <code>1 2 3 4 5</code>")
    except Exception as e:
        bot.send_message(uid, f"❌ Gagal mengirim OTP. Error: {str(e)}\nUlangi lagi dengan /register")
        user_login_state.pop(uid, None)


@bot.message_handler(func=lambda msg: user_login_state.get(msg.from_user.id, {}).get("step") == "INPUT_OTP")
def handle_otp_input(message):
    uid = message.from_user.id
    state = user_login_state[uid]
    otp_code = message.text.strip().replace(" ", "") # bersihkan spasi jika ada

    bot.reply_to(message, "⚡ Memverifikasi kode OTP Anda...")
    
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
        
        # Simpan konfigurasi sukses ke database JSON
        db = load_db()
        db["users"][str(uid)] = {
            "api_id": state["api_id"],
            "api_hash": state["api_hash"],
            "phone": state["phone"],
            "name": me.first_name,
            "username": me.username or ""
        }
        save_db(db)
        
        bot.send_message(uid, f"🎉 <b>Pendaftaran Berhasil!</b>\n\nAkun Anda: <b>{me.first_name}</b> (@{me.username}) telah aktif sebagai Userbot.\nSekarang Anda bisa mulai menggunakan perintah /gcastmassal untuk menyebarkan pesan otomatis.")
        
        # Notifikasi sukses login ke Owner
        owner_notif = (f"🚀 <b>Userbot Baru Aktif!</b>\n\n"
                       f"👤 User: {me.first_name} (@{me.username})\n"
                       f"🆔 ID: <code>{uid}</code>\n"
                       f"📱 Phone: {state['phone']}")
        bot.send_message(OWNER_ID, owner_notif)
        
    except Exception as e:
        bot.send_message(uid, f"❌ Gagal Verifikasi OTP. Error: {str(e)}\nSilakan ulangi proses dengan /register")
    finally:
        await client.disconnect()
        user_login_state.pop(uid, None)

# ── Fitur Broadcast Massal Otomatis (Akses Mandiri) ───────────────────

@bot.message_handler(commands=["gcastmassal"])
def cmd_gcast_massal(message):
    uid = str(message.from_user.id)
    db = load_db()
    
    if uid not in db["users"]:
        return bot.reply_to(message, "❌ Akun Anda belum terdaftar! Silakan ketik /register terlebih dahulu.")
        
    parts = message.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return bot.reply_to(message, "❌ Cara pakai:\n<code>/gcastmassal Teks Pesan Iklan Anda</code>")
        
    pesan_iklan = parts[1].strip()
    bot.reply_to(message, "📡 Menghubungkan ke sistem Userbot Anda... Proses broadcast akan segera berjalan di background.")
    
    # Jalankan proses broadcast userbot di thread terpisah agar bot utama tidak hang
    user_data = db["users"][uid]
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_async_broadcast, args=(loop, uid, user_data, pesan_iklan))
    t.start()

def run_async_broadcast(loop, uid, user_data, pesan):
    loop.run_until_complete(async_userbot_broadcast(uid, user_data, pesan))

async def async_userbot_broadcast(uid, user_data, pesan):
    session_name = f"sessions/user_{uid}"
    client = Client(session_name, api_id=user_data["api_id"], api_hash=user_data["api_hash"])
    
    # Contoh target username grup publik tujuan (Bisa dikembangkan menggunakan database grup dinamis)
    target_groups = ["grup_diskusi_publik_1", "pasar_indonesia_grup", "komunitas_crypto_id"] 
    
    try:
        await client.connect()
        sukses = 0
        
        for username in target_groups:
            try:
                # Cari dan join otomatis tanpa harus diundang
                chat = await client.join_chat(username)
                await client.send_message(chat.id, pesan)
                sukses += 1
                await asyncio.sleep(7) # Jeda waktu aman anti-banned
            except Exception:
                pass
                
        bot.send_message(uid, f"✅ <b>Broadcast Selesai!</b>\nPesan terkirim ke {sukses} grup publik.")
    except Exception as e:
        bot.send_message(uid, f"❌ Userbot Anda mengalami kendala koneksi: {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("🤖 Bot Utama & System Hybrid Aktif...")
    bot.infinity_polling()
