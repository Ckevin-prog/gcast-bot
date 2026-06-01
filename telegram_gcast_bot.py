"""
Telegram GCast Bot — menggunakan pyTelegramBotAPI
===================================================
Install: pip install pyTelegramBotAPI

Perintah:
  /start          → Daftar sebagai penerima broadcast
  /gcast <pesan>  → Broadcast ke semua user (admin only)
  /stats          → Jumlah user terdaftar (admin only)
"""

import telebot
import json
import os
import time
from datetime import datetime

# ─────────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────────
BOT_TOKEN = "8665011485:AAEbubrLFGrG6ErO06FHhXPKwRtGA1lm7cM"   # Token dari @BotFather
ADMIN_IDS = [7240245056]             # User ID admin (integer)
DB_FILE   = "users.json"
# ─────────────────────────────────────────────

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


# ── Database JSON ──────────────────────────────

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def register_user(user):
    users = load_users()
    uid = str(user.id)
    is_new = uid not in users
    users[uid] = {
        "id":         user.id,
        "username":   user.username or "",
        "first_name": user.first_name or "",
        "joined":     datetime.now().isoformat(),
    }
    save_users(users)
    return is_new

def get_all_user_ids():
    return [int(k) for k in load_users().keys()]

def remove_user(user_id):
    users = load_users()
    users.pop(str(user_id), None)
    save_users(users)

def is_admin(user_id):
    return user_id in ADMIN_IDS


# ── Handlers ───────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user = message.from_user
    is_new = register_user(user)
    if is_new:
        text = f"👋 Halo, <b>{user.first_name}</b>!\nKamu berhasil terdaftar dan akan menerima broadcast."
    else:
        text = f"👋 Halo lagi, <b>{user.first_name}</b>! Kamu sudah terdaftar."
    bot.reply_to(message, text)


@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Kamu tidak memiliki akses.")
        return
    total = len(get_all_user_ids())
    bot.reply_to(message, f"📊 <b>Total user terdaftar: {total}</b>")


@bot.message_handler(commands=["gcast"])
def cmd_gcast(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "⛔ Kamu tidak memiliki akses.")
        return

    # Ambil teks setelah /gcast
    parts = message.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message,
            "❌ Cara pakai:\n<code>/gcast Pesan yang ingin dikirim</code>")
        return

    teks     = parts[1].strip()
    user_ids = get_all_user_ids()
    total    = len(user_ids)

    if total == 0:
        bot.reply_to(message, "⚠️ Belum ada user yang terdaftar.")
        return

    status = bot.reply_to(message, f"📡 Memulai broadcast ke <b>{total}</b> user...")

    success = failed = blocked = 0

    for i, target_id in enumerate(user_ids, start=1):
        try:
            bot.send_message(target_id, teks)
            success += 1
        except telebot.apihelper.ApiTelegramException as e:
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                blocked += 1
                remove_user(target_id)
            else:
                failed += 1
        except Exception:
            failed += 1

        # Update status setiap 20 user
        if i % 20 == 0 or i == total:
            try:
                bot.edit_message_text(
                    f"📡 Progress: <b>{i}/{total}</b>\n"
                    f"✅ Berhasil: {success} | 🚫 Diblokir: {blocked} | ❌ Gagal: {failed}",
                    chat_id=status.chat.id,
                    message_id=status.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

        time.sleep(0.05)  # hindari rate limit

    bot.edit_message_text(
        f"✅ <b>Broadcast selesai!</b>\n\n"
        f"📊 Hasil:\n"
        f"  • Berhasil : <b>{success}</b>\n"
        f"  • Diblokir : <b>{blocked}</b> (dihapus dari DB)\n"
        f"  • Gagal    : <b>{failed}</b>\n"
        f"  • Total    : <b>{total}</b>",
        chat_id=status.chat.id,
        message_id=status.message_id,
        parse_mode="HTML",
    )


# ── Jalankan Bot ───────────────────────────────

if __name__ == "__main__":
    if "ISI_TOKEN" in BOT_TOKEN:
        raise ValueError("❌ Isi BOT_TOKEN terlebih dahulu!")
    if ADMIN_IDS == [123456789]:
        raise ValueError("❌ Isi ADMIN_IDS dengan user_id Telegram kamu!")

    print("✅ Bot berjalan... tekan Ctrl+C untuk berhenti.")
    bot.infinity_polling()


