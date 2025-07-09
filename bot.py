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
OWNER_USERNAME = "yakayuhq"  # Ton pseudo Telegram pour /dmall et /clean

# Charger les données utilisateurs
try:
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
except:
    user_data = {}

def save_data():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f)

# Nettoyer les users qui ont quitté le canal
async def clean_left_users(context: ContextTypes.DEFAULT_TYPE):
    to_remove = []
    for user_id in list(user_data.keys()):
        try:
            member = await context.bot.get_chat_member(chat_id=CANAL_USERNAME, user_id=int(user_id))
            if member.status in ['left', 'kicked']:
                to_remove.append(user_id)
        except Exception:
            to_remove.append(user_id)

    for user_id in to_remove:
        user_data.pop(user_id, None)

    if to_remove:
        save_data()
    return len(to_remove)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or "Utilisateur"

    # Nettoyage au lancement
    await clean_left_users(context)

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

    welcome_message = f"""
<b>👋 Bonjour <i>{username}</i> !</b>

Bienvenue sur la <b>passerelle officielle</b> pour accéder au canal de <b>YakayUHQ</b> 🔐✨, le meilleur vendeur de logs Telegram.

Pour rejoindre le canal, clique sur le bouton "Rejoindre le canal" ci-dessous ⬇️

Pour me contacter directement, clique sur le bouton "Me contacter" juste en dessous 📩

---

Merci de ta confiance, et à très vite dans le canal ! 🚀
"""

    await update.message.reply_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

# Rejoindre canal
async def handle_join_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    now = time.time()

    await query.answer()

    if now < user_data.get(user_id, {}).get("blocked_until", 0):
        await query.message.reply_text("🚫 Tu as échoué trop de fois. Réessaie plus tard.", parse_mode="HTML")
        return

    try:
        member = await context.bot.get_chat_member(chat_id=CANAL_USERNAME, user_id=query.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            await query.message.reply_text("✅ Tu es déjà membre du canal.", parse_mode="HTML")
            return
    except:
        pass

    a, b = random.randint(1, 9), random.randint(1, 9)
    correct = a + b
    options = [correct] + random.sample(
        [x for x in range(correct - 3, correct + 4) if x != correct],
        3
    )
    random.shuffle(options)

    user_data.setdefault(user_id, {})
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
            text=f"✅ Bien joué ! Voici ton lien pour rejoindre le canal :\n{invite.invite_link}",
            parse_mode="HTML"
        )
    else:
        user_data[user_id]["attempts"] = user_data[user_id].get("attempts", 0) + 1
        attempts_left = 3 - user_data[user_id]["attempts"]

        if attempts_left > 0:
            await context.bot.send_message(
                chat_id=answer.user.id,
                text=f"❌ Mauvaise réponse. Il te reste {attempts_left} essai(s).",
                parse_mode="HTML"
            )
        else:
            strike = user_data[user_id].get("strike_level", 1)
            ban_duration = 2 * 3600 * (2 ** (strike - 1))
            user_data[user_id]["blocked_until"] = time.time() + ban_duration
            user_data[user_id]["attempts"] = 0
            user_data[user_id]["strike_level"] = strike + 1
            await context.bot.send_message(
                chat_id=answer.user.id,
                text=f"🚫 Tu as échoué 3 fois. Tu es bloqué pour {ban_duration // 3600} heure(s).",
                parse_mode="HTML"
            )
        save_data()

# Commande /dmall réservée au propriétaire
async def dmall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != OWNER_USERNAME:
        await update.message.reply_text("❌ Cette commande est réservée au propriétaire du bot.", parse_mode="HTML")
        return

    if not context.args:
        await update.message.reply_text("Usage : /dmall [message]", parse_mode="HTML")
        return

    message = " ".join(context.args)
    failed = 0

    for user_id in user_data.keys():
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message, parse_mode="HTML")
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Message envoyé à {len(user_data) - failed} utilisateurs, {failed} échecs.",
        parse_mode="HTML"
    )

# Commande /clean réservée au propriétaire pour nettoyer la base manuellement
async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != OWNER_USERNAME:
        await update.message.reply_text("❌ Cette commande est réservée au propriétaire du bot.", parse_mode="HTML")
        return

    removed = await clean_left_users(context)
    await update.message.reply_text(f"🧹 Nettoyage terminé. {removed} utilisateur(s) supprimé(s) de la base.", parse_mode="HTML")

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_join_click, pattern="^join_request$"))
app.add_handler(PollAnswerHandler(handle_poll_answer))
app.add_handler(CommandHandler("dmall", dmall))
app.add_handler(CommandHandler("clean", clean))

app.run_polling()
