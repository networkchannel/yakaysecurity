import random
import json
import time
import os
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    Poll
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ContextTypes
)


BOT_TOKEN = os.getenv("BOT_TOKEN")

CANAL_USERNAME = "@yakayshop"  # Obligatoire pour créer des liens
CONTACT_URL = "https://t.me/yakayuhq"
USER_DATA_FILE = "users_data.json"

# Charger les données utilisateurs
try:
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
except:
    user_data = {}

def save_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_data:
        user_data[user_id] = {
            "attempts": 0,
            "blocked_until": 0,
            "strike_level": 1  # Pour ban progressif
        }
        save_data()

    keyboard = [
        [InlineKeyboardButton("🔐 Rejoindre le canal", callback_data="join_request")],
        [InlineKeyboardButton("👤 Me contacter", url=CONTACT_URL)]
    ]
    await update.message.reply_text(
        "👋 Bienvenue !\nTu es bien enregistré. Pour rejoindre le canal, tu dois résoudre un petit CAPTCHA.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Rejoindre canal
async def handle_join_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    now = time.time()

    await query.answer()

    # Blocage actif ?
    if now < user_data[user_id]["blocked_until"]:
        await query.message.reply_text("🚫 Tu as échoué trop de fois. Réessaie plus tard.")
        return

    # Vérifie s'il est déjà dans le canal
    try:
        member = await context.bot.get_chat_member(chat_id=CANAL_USERNAME, user_id=query.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            await query.message.reply_text("✅ Tu es déjà membre du canal.")
            return
    except:
        pass  # Peut arriver si canal privé mal configuré

    # CAPTCHA
    a, b = random.randint(1, 9), random.randint(1, 9)
    correct = a + b
    options = [correct] + random.sample(
        [x for x in range(correct - 3, correct + 4) if x != correct],
        3
    )
    random.shuffle(options)

    user_data[user_id]["captcha_answer"] = correct
    user_data[user_id]["captcha_options"] = options
    save_data()

    await context.bot.send_poll(
        chat_id=query.from_user.id,
        question=f"🧠 Combien font {a} + {b} ?",
        options=[str(opt) for opt in options],
        type=Poll.QUIZ,
        correct_option_id=options.index(correct),
        is_anonymous=False,
        # ❌ Suppression de l’explication pour éviter d'afficher "Bravo..." même en cas d'échec
        open_period=60
    )

# Réponse CAPTCHA
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = str(answer.user.id)
    correct_answer = user_data.get(user_id, {}).get("captcha_answer")
    options = user_data.get(user_id, {}).get("captcha_options", [])
    selected_index = answer.option_ids[0]
    selected_value = options[selected_index] if selected_index < len(options) else None

    if selected_value == correct_answer:
        user_data[user_id]["attempts"] = 0
        user_data[user_id]["strike_level"] = 1
        save_data()

        invite = await context.bot.create_chat_invite_link(
            chat_id=CANAL_USERNAME,
            member_limit=1,
            expire_date=int(time.time()) + 3600
        )
        await context.bot.send_message(
            chat_id=answer.user.id,
            text=f"✅ Bien joué ! Voici ton lien pour rejoindre le canal :\n{invite.invite_link}"
        )
    else:
        user_data[user_id]["attempts"] += 1
        attempts_left = 3 - user_data[user_id]["attempts"]

        if attempts_left > 0:
            await context.bot.send_message(
                chat_id=answer.user.id,
                text=f"❌ Mauvaise réponse. Il te reste {attempts_left} essai(s)."
            )
        else:
            # Ban exponentiel
            strike = user_data[user_id].get("strike_level", 1)
            ban_duration = 2 * 3600 * (2 ** (strike - 1))  # 2h, 4h, 8h, ...
            user_data[user_id]["blocked_until"] = time.time() + ban_duration
            user_data[user_id]["attempts"] = 0
            user_data[user_id]["strike_level"] = strike + 1
            await context.bot.send_message(
                chat_id=answer.user.id,
                text=f"🚫 Tu as échoué 3 fois. Tu es bloqué pour {ban_duration // 3600} heure(s)."
            )
        save_data()

# Main
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_join_click, pattern="^join_request$"))
app.add_handler(PollAnswerHandler(handle_poll_answer))
app.run_polling()
