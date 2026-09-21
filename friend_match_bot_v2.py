#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💞 Friend Match Bot  |  Do'stlik boti   (v2 - real users)
=========================================================
Project: "Design the Perfect Friend" (Unit 1-2)

How it works / Qanday ishlaydi
- Every person registers once: name, age, adjectives, hobbies, wanted / unwanted
  qualities and a 5-question compatibility test.
- 🌍 GLOBAL list: top matches (in %) among ALL registered users.
- 🔵 CIRCLES: a circle is a private group with a join code. At the end of
  registration you can create your own circle, join one with a code, or skip.
  Every circle has its own separate top list.
- 🤝 Friend requests: contact details (@username) are shared ONLY after both
  people agree.
- 🌐 Two languages (Uzbek / English) + command panel (☰ Menu button).

Install:   pip install "python-telegram-bot>=21"
Run:       BOT_TOKEN=your_token_here python friend_match_bot_v2.py
Optional:  DATA_DIR=/data   (folder for the database; use a persistent Volume on a server)
NEVER write your real token into this file or upload it to GitHub!
"""

import html
import json
import logging
import os
import random
import secrets
import sqlite3

from telegram import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN", "")
DATA_DIR = os.getenv("DATA_DIR", ".")
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "friend_match.db"))

GLOBAL_TOP = 8      # how many people the global list shows
CIRCLE_TOP = 8      # how many people a circle list shows
MAX_CIRCLES = 5     # circles one person can be in

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO
)
log = logging.getLogger("friend_match_bot")


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS  (every bilingual text is a tuple: (English, Uzbek))
# ══════════════════════════════════════════════════════════════════════════════
def pick(pair, lang):
    return pair[0] if lang == "en" else pair[1]


def esc(s):
    return html.escape(str(s))


def bar(v):
    v = max(0, min(10, int(v)))
    return "█" * v + "░" * (10 - v)


# ══════════════════════════════════════════════════════════════════════════════
#  DATA: traits, hobbies
# ══════════════════════════════════════════════════════════════════════════════
# key: (English, Uzbek, is_positive)
TRAITS = {
    "outgoing": ("outgoing", "kirishimli", True),
    "imaginative": ("imaginative", "tasavvuri boy", True),
    "patient": ("patient", "sabrli", True),
    "honest": ("honest", "halol", True),
    "funny": ("funny", "hazilkash", True),
    "kind": ("kind", "mehribon", True),
    "creative": ("creative", "ijodkor", True),
    "calm": ("calm", "xotirjam", True),
    "energetic": ("energetic", "serharakat", True),
    "organized": ("organized", "tartibli", True),
    "loyal": ("loyal", "sadoqatli", True),
    "curious": ("curious", "qiziquvchan", True),
    # negative traits (most have un- / in- / dis- prefixes!)
    "impatient": ("impatient", "sabrsiz", False),
    "unfriendly": ("unfriendly", "sovuqmuomala", False),
    "dishonest": ("dishonest", "yolg'onchi", False),
    "disorganized": ("disorganized", "tartibsiz", False),
    "insensitive": ("insensitive", "his-tuyg'usiz", False),
    "unreliable": ("unreliable", "ishonchsiz", False),
}

# which positive trait "fixes" a negative one (used for the personality score)
FIXES = {
    "impatient": "patient",
    "disorganized": "organized",
    "dishonest": "honest",
    "unfriendly": "kind",
    "insensitive": "kind",
    "unreliable": "loyal",
}

# key: (emoji, English, Uzbek)
HOBBIES = {
    "football": ("⚽", "football", "futbol"),
    "reading": ("📚", "reading", "kitob o'qish"),
    "painting": ("🎨", "painting", "rasm chizish"),
    "music": ("🎵", "music", "musiqa"),
    "gaming": ("🎮", "gaming", "o'yinlar"),
    "cooking": ("🍳", "cooking", "pazandachilik"),
    "hiking": ("🥾", "hiking", "tog'ga yurish"),
    "coding": ("💻", "coding", "dasturlash"),
    "photography": ("📷", "photography", "fotografiya"),
    "dancing": ("💃", "dancing", "raqs"),
    "volunteering": ("🤝", "volunteering", "volontyorlik"),
    "chess": ("♟️", "chess", "shaxmat"),
    "swimming": ("🏊", "swimming", "suzish"),
    "travel": ("✈️", "travelling", "sayohat"),
}


def trait_label(key, lang):
    en, uz, _ = TRAITS[key]
    return en if lang == "en" else f"{en} · {uz}"


def hobby_label(key, lang):
    emoji, en, uz = HOBBIES[key]
    return f"{emoji} {en}" if lang == "en" else f"{emoji} {en} · {uz}"


# ══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY TEST  (replace with your GROUP'S OWN questions for Stage 3!)
#  Options go from gentle / reserved (A) to direct / bold (C).
# ══════════════════════════════════════════════════════════════════════════════
QUESTIONS = [
    {   # Trust
        "q": ("A friend tells you a secret. Later, a classmate asks you about it. What do you do?",
              "Do'stingiz sizga sir aytdi. Keyin sinfdoshingiz bu haqda so'radi. Nima qilasiz?"),
        "opts": [
            ("I quietly change the subject.", "Gapni jimgina boshqa tomonga burib yuboraman."),
            ("I smile and say: \"Ask them yourself.\"", "Jilmayib: \"O'zidan so'ra\", deyman."),
            ("I say clearly: \"That's private and I won't share it.\"",
             "Aniq aytaman: \"Bu shaxsiy, men aytmayman.\""),
        ],
    },
    {   # Trust
        "q": ("Your friend forgets your birthday. How do you react?",
              "Do'stingiz tug'ilgan kuningizni unutdi. Qanday munosabat bildirasiz?"),
        "opts": [
            ("I say nothing and hope they remember later.",
             "Hech narsa demayman, keyin eslar deb umid qilaman."),
            ("I make a small joke about it.", "Bu haqda kichik hazil qilaman."),
            ("I tell them honestly that I felt a bit hurt.",
             "Ozgina xafa bo'lganimni ochiq aytaman."),
        ],
    },
    {   # Communication
        "q": ("You and your friend want to watch different films. What happens next?",
              "Siz va do'stingiz turli filmlarni ko'rmoqchisiz. Keyin nima bo'ladi?"),
        "opts": [
            ("I let my friend choose to keep the peace.",
             "Tinchlik uchun tanlovni do'stimga qoldiraman."),
            ("We take turns or pick a third film together.",
             "Navbatma-navbat tanlaymiz yoki uchinchi filmni birga tanlaymiz."),
            ("I explain why my film is better and try to convince them.",
             "Mening filmim nima uchun yaxshiroq ekanini tushuntirib, ishontirishga harakat qilaman."),
        ],
    },
    {   # Communication
        "q": ("Your friend looks sad but says \"I'm fine\". What do you do?",
              "Do'stingiz xafa ko'rinadi, lekin \"Yaxshiman\" deydi. Nima qilasiz?"),
        "opts": [
            ("I give them space until they are ready to talk.",
             "Gaplashishga tayyor bo'lguncha ularga erkinlik beraman."),
            ("I send a kind message: \"I'm here if you need me.\"",
             "Mehribon xabar yuboraman: \"Kerak bo'lsam, men shu yerdaman.\""),
            ("I sit next to them and ask directly what happened.",
             "Yoniga o'tirib, nima bo'lganini to'g'ridan-to'g'ri so'rayman."),
        ],
    },
    {   # Fun together
        "q": ("You have a free Saturday. What sounds best?",
              "Shanba kuni bo'sh. Qaysi reja yoqadi?"),
        "opts": [
            ("A quiet day: books, films and hot chocolate at home.",
             "Sokin kun: uyda kitob, film va issiq shokolad."),
            ("A relaxed walk in the park and a café.",
             "Parkda sayr va kafega borish."),
            ("An active adventure: a hike, a sports match or something new.",
             "Faol sarguzasht: tog'ga chiqish, sport o'yini yoki yangi narsa."),
        ],
    },
]

CATS = ["personality", "interests", "trust", "communication", "fun"]

STRONG = {
    "personality": ("their personalities fit together well",
                    "ularning xarakterlari bir-biriga juda mos"),
    "interests": ("they share interests such as {hobbies}",
                  "ularda {hobbies} kabi umumiy qiziqishlar bor"),
    "trust": ("they treat trust and honesty in a similar way",
              "ular ishonch va halollikka o'xshash qaraydi"),
    "communication": ("they communicate and solve problems in a similar way",
                      "ular muloqot qilish va muammolarni hal qilishda o'xshash"),
    "fun": ("they enjoy the same kind of free time",
            "ularning bo'sh vaqtni o'tkazish uslubi o'xshash"),
}
WEAK = {
    "personality": ("their personalities are quite different",
                    "ularning xarakterlari ancha farq qiladi"),
    "interests": ("they do not share many hobbies",
                  "ularning umumiy hobbilari kam"),
    "trust": ("they see honesty and loyalty in different ways",
              "ular halollik va sadoqatga turlicha qaraydi"),
    "communication": ("they solve disagreements in different ways",
                      "ular kelishmovchiliklarni turlicha hal qiladi"),
    "fun": ("they want different kinds of weekends",
            "ular dam olish kunlarini turlicha o'tkazishni xohlaydi"),
}
# thresholds are in PERCENT
RATINGS = [
    (84, ("Perfect match ✨", "Ajoyib juftlik ✨")),
    (68, ("Great friends 😄", "Zo'r do'stlar 😄")),
    (52, ("Good potential 🙂", "Yaxshi imkoniyat 🙂")),
    (0, ("Needs effort 🤝", "Harakat kerak 🤝")),
]

TIPS = [
    ("A good friend listens more than they talk.",
     "Yaxshi do'st gapirgandan ko'ra ko'proq tinglaydi."),
    ("Be honest, but be kind. Honesty without kindness can hurt.",
     "Halol bo'ling, lekin mehribon ham bo'ling. Mehrsiz halollik og'ritishi mumkin."),
    ("Keep your promises. Trust takes months to build and seconds to lose.",
     "Va'dangizda turing. Ishonch oylar davomida quriladi, lekin bir zumda yo'qoladi."),
    ("Different personalities can be a great match: a patient friend balances an impatient one.",
     "Turli xarakterlar ajoyib juftlik bo'lishi mumkin: sabrli do'st sabrsiz do'stni muvozanatlaydi."),
    ("Don't mind saying sorry first, and avoid arguing about small things.",
     "Birinchi bo'lib uzr so'rashdan qaytmang va mayda narsalar ustida tortishishdan qoching."),
    ("Try new things together: shared adventures make strong friendships.",
     "Birga yangi narsalarni sinab ko'ring: umumiy sarguzashtlar do'stlikni mustahkamlaydi."),
    ("Celebrate your friend's success. Real friends are happy for each other.",
     "Do'stingizning yutug'idan xursand bo'ling. Haqiqiy do'stlar bir-biri uchun quvonadi."),
    ("Put your phone away sometimes and enjoy spending time face to face.",
     "Ba'zan telefonni qo'yib, yuzma-yuz vaqt o'tkazishdan zavqlaning."),
]


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE (SQLite)
# ══════════════════════════════════════════════════════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    name       TEXT NOT NULL,
    age        INTEGER,
    traits     TEXT NOT NULL,
    hobbies    TEXT NOT NULL,
    wants      TEXT NOT NULL,
    avoid      TEXT NOT NULL,
    answers    TEXT NOT NULL,
    lang       TEXT DEFAULT 'uz',
    visible    INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS circles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    code     TEXT UNIQUE NOT NULL,
    owner_id INTEGER
);
CREATE TABLE IF NOT EXISTS members (
    circle_id INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    PRIMARY KEY (circle_id, user_id)
);
CREATE TABLE IF NOT EXISTS requests (
    from_id INTEGER NOT NULL,
    to_id   INTEGER NOT NULL,
    status  TEXT DEFAULT 'pending',
    PRIMARY KEY (from_id, to_id)
);
"""
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

db = None


def init_db():
    global db
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.commit()


def row_to_user(r):
    if r is None:
        return None
    return {
        "id": r["user_id"], "username": r["username"], "name": r["name"], "age": r["age"],
        "traits": json.loads(r["traits"]), "hobbies": json.loads(r["hobbies"]),
        "wants": json.loads(r["wants"]), "avoid": json.loads(r["avoid"]),
        "answers": json.loads(r["answers"]), "lang": r["lang"] or "uz",
        "visible": bool(r["visible"]),
    }


def get_user(uid):
    return row_to_user(db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone())


def save_user(uid, username, p, answers, lang):
    db.execute(
        """INSERT INTO users (user_id, username, name, age, traits, hobbies, wants, avoid, answers, lang)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             username=excluded.username, name=excluded.name, age=excluded.age,
             traits=excluded.traits, hobbies=excluded.hobbies, wants=excluded.wants,
             avoid=excluded.avoid, answers=excluded.answers, lang=excluded.lang""",
        (uid, username, p["name"], p["age"], json.dumps(p["traits"]), json.dumps(p["hobbies"]),
         json.dumps(p["wants"]), json.dumps(p["avoid"]), json.dumps(answers), lang),
    )
    db.commit()


def update_answers(uid, answers):
    db.execute("UPDATE users SET answers=? WHERE user_id=?", (json.dumps(answers), uid))
    db.commit()


def touch_user(uid, username=None, lang=None):
    if username is not None:
        db.execute("UPDATE users SET username=? WHERE user_id=?", (username, uid))
    if lang is not None:
        db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))
    db.commit()


def set_visible(uid, value):
    db.execute("UPDATE users SET visible=? WHERE user_id=?", (1 if value else 0, uid))
    db.commit()


def global_others(uid):
    rows = db.execute("SELECT * FROM users WHERE user_id != ? AND visible = 1", (uid,)).fetchall()
    return [row_to_user(r) for r in rows]


# ---- circles ---------------------------------------------------------------
def create_circle(owner_id, name):
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not db.execute("SELECT 1 FROM circles WHERE code=?", (code,)).fetchone():
            break
    cur = db.execute("INSERT INTO circles (name, code, owner_id) VALUES (?,?,?)", (name, code, owner_id))
    cid = cur.lastrowid
    db.execute("INSERT INTO members (circle_id, user_id) VALUES (?,?)", (cid, owner_id))
    db.commit()
    return cid, code


def get_circle(cid):
    return db.execute("SELECT * FROM circles WHERE id=?", (cid,)).fetchone()


def find_circle_by_code(code):
    return db.execute("SELECT * FROM circles WHERE code=?", (code,)).fetchone()


def is_member(cid, uid):
    return db.execute("SELECT 1 FROM members WHERE circle_id=? AND user_id=?", (cid, uid)).fetchone() is not None


def join_circle(cid, uid):
    db.execute("INSERT OR IGNORE INTO members (circle_id, user_id) VALUES (?,?)", (cid, uid))
    db.commit()


def my_circles(uid):
    return db.execute(
        "SELECT c.* FROM circles c JOIN members m ON m.circle_id = c.id WHERE m.user_id=? ORDER BY c.id",
        (uid,),
    ).fetchall()


def count_members(cid):
    return db.execute("SELECT COUNT(*) FROM members WHERE circle_id=?", (cid,)).fetchone()[0]


def circle_others(cid, uid):
    rows = db.execute(
        "SELECT u.* FROM users u JOIN members m ON m.user_id = u.user_id "
        "WHERE m.circle_id=? AND u.user_id != ?",
        (cid, uid),
    ).fetchall()
    return [row_to_user(r) for r in rows]


def leave_circle(cid, uid):
    db.execute("DELETE FROM members WHERE circle_id=? AND user_id=?", (cid, uid))
    if count_members(cid) == 0:
        db.execute("DELETE FROM circles WHERE id=?", (cid,))
    db.commit()


# ---- friend requests -------------------------------------------------------
def req_status(a, b):
    """Status from the point of view of user a about user b."""
    r1 = db.execute("SELECT status FROM requests WHERE from_id=? AND to_id=?", (a, b)).fetchone()
    r2 = db.execute("SELECT status FROM requests WHERE from_id=? AND to_id=?", (b, a)).fetchone()
    if (r1 and r1["status"] == "accepted") or (r2 and r2["status"] == "accepted"):
        return "friends"
    if r1:
        return "sent"          # pending or declined (the sender is never told about a decline)
    if r2 and r2["status"] == "pending":
        return "received"
    return None


def add_request(a, b):
    db.execute("INSERT OR REPLACE INTO requests (from_id, to_id, status) VALUES (?,?, 'pending')", (a, b))
    db.commit()


def set_request(from_id, to_id, status):
    db.execute("UPDATE requests SET status=? WHERE from_id=? AND to_id=?", (status, from_id, to_id))
    db.commit()


def friends_of(uid):
    rows = db.execute(
        """SELECT u.* FROM requests r
           JOIN users u ON u.user_id = CASE WHEN r.from_id = ? THEN r.to_id ELSE r.from_id END
           WHERE r.status = 'accepted' AND (r.from_id = ? OR r.to_id = ?)""",
        (uid, uid, uid),
    ).fetchall()
    return [row_to_user(r) for r in rows]


def contact(u):
    if u["username"]:
        return "@" + u["username"]
    return f'<a href="tg://user?id={u["id"]}">{esc(u["name"])}</a>'


# ══════════════════════════════════════════════════════════════════════════════
#  SCORING  (Personality, Common interests, Trust, Communication, Fun → /50 → %)
# ══════════════════════════════════════════════════════════════════════════════
def _personality_directional(a, b):
    """How well person b fits what person a wants."""
    bt = set(b["traits"])
    overlap = len(set(a["wants"]) & bt)
    fixes = sum(1 for t in a["traits"] if t in FIXES and FIXES[t] in bt)
    penalty = len(set(a["avoid"]) & bt)
    return max(0, min(10, min(8, 2 * overlap) + min(2, fixes) - 3 * penalty))


def pair_score(a, b):
    p_ab, p_ba = _personality_directional(a, b), _personality_directional(b, a)
    personality = int((p_ab + p_ba) / 2 + 0.5)

    common = sorted(set(a["hobbies"]) & set(b["hobbies"]))
    interests = [2, 5, 8, 10][min(len(common), 3)]

    pts = [{0: 5, 1: 3, 2: 1}[abs(x - y)] for x, y in zip(a["answers"], b["answers"])]
    trust, communication, fun = pts[0] + pts[1], pts[2] + pts[3], pts[4] * 2

    total = personality + interests + trust + communication + fun
    return {
        "personality": personality, "interests": interests, "trust": trust,
        "communication": communication, "fun": fun, "total": total,
        "pct": total * 2, "common": common,
    }


def rating(pct, lang):
    for threshold, pair in RATINGS:
        if pct >= threshold:
            return pick(pair, lang)
    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND PANEL
# ══════════════════════════════════════════════════════════════════════════════
COMMANDS = [
    ("start", ("Start the bot", "Botni ishga tushirish")),
    ("menu", ("Main menu", "Asosiy menyu")),
    ("profile", ("My profile / register", "Profilim / ro'yxatdan o'tish")),
    ("test", ("Retake compatibility test", "Moslik testini qayta topshirish")),
    ("match", ("Global matches (top list)", "Global moslik (eng yaxshilar)")),
    ("circles", ("My circles", "Mening doiralarim")),
    ("friends", ("My friends", "Mening do'stlarim")),
    ("project", ("Project checklist", "Loyiha ro'yxati")),
    ("tip", ("Friendship tip", "Do'stlik maslahati")),
    ("language", ("Change language", "Tilni almashtirish")),
    ("help", ("Help", "Yordam")),
    ("cancel", ("Cancel current action", "Joriy amalni bekor qilish")),
]


def commands_for(lang):
    i = 0 if lang == "en" else 1
    return [BotCommand(c, d[i]) for c, d in COMMANDS]


async def post_init(app: Application):
    """Set the command panel (☰ Menu button). Default = Uzbek, English for English clients."""
    await app.bot.set_my_commands(commands_for("uz"))
    await app.bot.set_my_commands(commands_for("uz"), language_code="uz")
    await app.bot.set_my_commands(commands_for("en"), language_code="en")


# ══════════════════════════════════════════════════════════════════════════════
#  TEXTS  (English, Uzbek)
# ══════════════════════════════════════════════════════════════════════════════
T = {
    "choose_lang": ("🌐 Choose your language / Tilni tanlang:",) * 2,
    "welcome": (
        "👋 Hi! I'm the <b>Friend Match Bot</b> 💞\n\n"
        "I help teenagers find friends with a compatible personality.\n"
        "• Register once (profile + 5-question test)\n"
        "• 🌍 See your top matches among all users, in %\n"
        "• 🔵 Create or join a private <b>circle</b> with its own top list\n"
        "• 🤝 Send friend requests. Contacts are shared only when both agree\n\n"
        "Start with <b>👤 My profile</b>. You can also use the <b>Menu</b> button (☰) "
        "next to the message box to open the command panel.",
        "👋 Salom! Men <b>Friend Match Bot</b>man 💞\n\n"
        "O'smirlarga xarakteri mos do'st topishda yordam beraman.\n"
        "• Bir marta ro'yxatdan o'ting (profil + 5 savolli test)\n"
        "• 🌍 Barcha foydalanuvchilar orasidan eng mos odamlarni foizda ko'ring\n"
        "• 🔵 O'z <b>doirangizni</b> yarating yoki kod bilan qo'shiling, har bir doiraning alohida reytingi bor\n"
        "• 🤝 Do'stlik so'rovi yuboring. Kontaktlar faqat ikkala tomon rozi bo'lsa beriladi\n\n"
        "<b>👤 Profilim</b> dan boshlang. Buyruqlar paneli uchun xabar yozish maydoni "
        "yonidagi <b>Menu</b> (☰) tugmasidan ham foydalanishingiz mumkin.",
    ),
    "menu_title": ("🏠 <b>Main menu</b>\nChoose what you want to do:",
                   "🏠 <b>Asosiy menyu</b>\nNima qilmoqchisiz?"),
    # buttons
    "btn_profile": ("👤 My profile", "👤 Profilim"),
    "btn_test": ("🧪 Retake test", "🧪 Testni qayta topshirish"),
    "btn_match": ("🌍 Global matches", "🌍 Global moslik"),
    "btn_circles": ("🔵 My circles", "🔵 Doiralarim"),
    "btn_friends": ("🤝 My friends", "🤝 Do'stlarim"),
    "btn_project": ("📋 Project checklist", "📋 Loyiha ro'yxati"),
    "btn_tip": ("💡 Friendship tip", "💡 Do'stlik maslahati"),
    "btn_lang": ("🌐 Language", "🌐 Til"),
    "btn_help": ("❓ Help", "❓ Yordam"),
    "btn_menu": ("🏠 Menu", "🏠 Menyu"),
    "btn_done": ("✅ Done", "✅ Tayyor"),
    "btn_back": ("⬅️ Back to the list", "⬅️ Ro'yxatga qaytish"),
    "btn_send_req": ("🤝 Send friend request", "🤝 Do'stlik so'rovini yuborish"),
    "btn_req_sent": ("⏳ Request sent", "⏳ So'rov yuborilgan"),
    "btn_friends_already": ("✅ You are friends", "✅ Siz do'stsiz"),
    "btn_accept_their": ("✅ Accept their request", "✅ So'rovni qabul qilish"),
    "btn_accept": ("✅ Accept", "✅ Qabul qilish"),
    "btn_decline": ("❌ Decline", "❌ Rad etish"),
    "btn_circ_new": ("➕ Create my circle", "➕ O'z doiramni yaratish"),
    "btn_circ_join": ("🔑 Join with a code", "🔑 Kod bilan qo'shilish"),
    "btn_skip": ("⏭ Skip", "⏭ Keyinroq"),
    "btn_leave": ("🚪 Leave circle", "🚪 Doiradan chiqish"),
    "btn_yes": ("✅ Yes", "✅ Ha"),
    "btn_no": ("❌ No", "❌ Yo'q"),
    "btn_redo": ("✏️ Register again", "✏️ Qayta to'ldirish"),
    "btn_vis_hide": ("🙈 Hide me from Global list", "🙈 Globaldan yashirish"),
    "btn_vis_show": ("👁 Show me in Global list", "👁 Globalda ko'rinish"),
    "btn_view_circle": ("🔵 Open the circle", "🔵 Doirani ochish"),
    "btn_circles_back": ("⬅️ My circles", "⬅️ Doiralarim"),
    "btn_show_global": ("🌍 Show global matches", "🌍 Global natijalarni ko'rish"),
    # registration wizard
    "ask_name": (
        "👤 <b>Step 1/6 — Name</b>\nWhat name should other people see? (A nickname is fine.)",
        "👤 <b>1/6-qadam — Ism</b>\nBoshqalar sizni qanday ism bilan ko'rsin? (Laqab ham bo'ladi.)",
    ),
    "ask_age": ("🎂 <b>Step 2/6 — Age</b>\nHow old are you? (10–25)\nYour age is never shown to other users.",
                "🎂 <b>2/6-qadam — Yosh</b>\nNecha yoshdasiz? (10–25)\nYoshingiz boshqalarga ko'rsatilmaydi."),
    "bad_name": ("Please write a name between 2 and 20 characters.",
                 "Iltimos, 2 dan 20 tagacha belgidan iborat ism yozing."),
    "bad_age": ("Please send a number from 10 to 25.",
                "Iltimos, 10 dan 25 gacha son yuboring."),
    "ask_traits": (
        "🧩 <b>Step 3/6 — Personality</b>\nChoose {mn}–{mx} adjectives that describe you. "
        "Try to include some with un-, in-, dis- (like <i>impatient</i>)!",
        "🧩 <b>3/6-qadam — Xarakter</b>\nO'zingizni ifodalovchi {mn}–{mx} ta sifatni tanlang. "
        "un-, in-, dis- bilan boshlanadiganlardan ham tanlang (masalan, <i>impatient</i>)!",
    ),
    "ask_hobbies": ("🎯 <b>Step 4/6 — Hobbies</b>\nChoose {mn}–{mx} hobbies.",
                    "🎯 <b>4/6-qadam — Hobbilar</b>\n{mn}–{mx} ta hobbini tanlang."),
    "ask_wants": (
        "💖 <b>Step 5/6 — Qualities you WANT in a friend</b>\nChoose {mn}–{mx} qualities.",
        "💖 <b>5/6-qadam — Do'stda bo'lishi KERAK sifatlar</b>\n{mn}–{mx} ta sifatni tanlang.",
    ),
    "ask_avoid": (
        "🚫 <b>Step 6/6 — Qualities you do NOT want</b>\nChoose {mn}–{mx} qualities.",
        "🚫 <b>6/6-qadam — Do'stda bo'lmasligi KERAK sifatlar</b>\n{mn}–{mx} ta sifatni tanlang.",
    ),
    "need_min": ("Please choose at least {mn}.", "Kamida {mn} ta tanlang."),
    "limit_reached": ("You can choose up to {mx} only.", "Ko'pi bilan {mx} ta tanlash mumkin."),
    "stale": ("This button is old. Please start again from the menu.",
              "Bu tugma eskirgan. Menyudan qaytadan boshlang."),
    "prof_ready": (
        "✅ <b>Profile ready!</b>\n\n{card}\n\nLast step: 5 quick test questions 👇",
        "✅ <b>Profil tayyor!</b>\n\n{card}\n\nOxirgi qadam: 5 ta qisqa test savoli 👇",
    ),
    "reg_done": (
        "🎉 <b>Registration complete!</b>\n"
        "You can already see your matches in the 🌍 <b>Global</b> list.\n\n"
        "One more optional thing: a <b>circle</b> is a private group with its own top list "
        "(for example, your class or your friends). Create your own circle or join an existing one with a code.",
        "🎉 <b>Ro'yxatdan o'tdingiz!</b>\n"
        "Endi 🌍 <b>Global</b> ro'yxatda o'zingizga mos odamlarni ko'rishingiz mumkin.\n\n"
        "Yana bitta ixtiyoriy narsa: <b>doira</b> bu alohida reytingli yopiq guruh "
        "(masalan, sinfingiz yoki do'stlaringiz). O'z doirangizni yarating yoki mavjudiga kod bilan qo'shiling.",
    ),
    "test_updated": ("✅ <b>Test updated!</b>", "✅ <b>Test yangilandi!</b>"),
    "need_profile": ("First, register with your profile 👇", "Avval profil orqali ro'yxatdan o'ting 👇"),
    # own profile
    "lbl_traits": ("Personality", "Xarakter"),
    "lbl_hobbies": ("Hobbies", "Hobbilar"),
    "lbl_wants": ("Wants in a friend", "Do'stda kerak"),
    "lbl_avoid": ("Does not want", "Do'stda kerak emas"),
    "lbl_age": ("Age", "Yosh"),
    "vis_on": ("👁 You are <b>visible</b> in the Global list.", "👁 Siz Global ro'yxatda <b>ko'rinasiz</b>."),
    "vis_off": ("🙈 You are <b>hidden</b> from the Global list (circle members still see you).",
                "🙈 Siz Global ro'yxatdan <b>yashirinsiz</b> (doira a'zolari sizni ko'radi)."),
    # test
    "test_title": ("🧪 <b>Friendship Compatibility Test</b> — question {i}/{n}",
                   "🧪 <b>Do'stlik mosligi testi</b> — {i}/{n}-savol"),
    # rankings
    "global_title": ("🌍 <b>Global matches</b> — top {n} among all users\nTap a name for details:",
                     "🌍 <b>Global moslik</b> — barcha foydalanuvchilar orasida top {n}\nBatafsil ma'lumot uchun ismni bosing:"),
    "no_users": ("No other users have registered yet. Invite your friends to the bot! 🚀",
                 "Hozircha boshqa foydalanuvchilar yo'q. Do'stlaringizni botga taklif qiling! 🚀"),
    "circles_title": ("🔵 <b>My circles</b>\nA circle is a private group. Only people with the code can join.",
                      "🔵 <b>Mening doiralarim</b>\nDoira yopiq guruh. Faqat kodi borlar qo'shila oladi."),
    "circles_none": ("You are not in any circle yet.", "Siz hali hech qaysi doirada emassiz."),
    "circle_header": ("🔵 <b>{name}</b> · {n} member(s)\nJoin code: <code>{code}</code>\nTop matches in this circle:",
                      "🔵 <b>{name}</b> · {n} a'zo\nQo'shilish kodi: <code>{code}</code>\nBu doiradagi eng mos odamlar:"),
    "circle_alone": ("You are the only member so far. Share the code with your friends!",
                     "Hozircha faqat o'zingiz borsiz. Kodni do'stlaringizga yuboring!"),
    "ask_circle_name": ("➕ Send a name for your new circle (2–25 characters).\n/cancel to stop.",
                        "➕ Yangi doira uchun nom yuboring (2–25 belgi).\nTo'xtatish uchun /cancel."),
    "bad_circle_name": ("The name must be 2–25 characters. Try again.",
                        "Nom 2–25 belgidan iborat bo'lishi kerak. Qayta yuboring."),
    "ask_circle_code": ("🔑 Send the 6-character circle code.\n/cancel to stop.",
                        "🔑 Doiraning 6 belgili kodini yuboring.\nTo'xtatish uchun /cancel."),
    "bad_code": ("No circle with this code. Check it and try again (or /cancel).",
                 "Bunday kodli doira topilmadi. Tekshirib qayta yuboring (yoki /cancel)."),
    "max_circles": ("You can be in up to {n} circles.", "Siz ko'pi bilan {n} ta doirada bo'lishingiz mumkin."),
    "already_member": ("You are already in this circle.", "Siz bu doirada allaqachon borsiz."),
    "circle_created": (
        "✅ Circle <b>{name}</b> created!\nJoin code: <code>{code}</code>\nShare this code with your friends.",
        "✅ <b>{name}</b> doirasi yaratildi!\nQo'shilish kodi: <code>{code}</code>\nBu kodni do'stlaringizga yuboring.",
    ),
    "circle_joined": ("✅ You joined <b>{name}</b>!", "✅ Siz <b>{name}</b> doirasiga qo'shildingiz!"),
    "leave_confirm": ("Leave the circle <b>{name}</b>?", "<b>{name}</b> doirasidan chiqasizmi?"),
    "left": ("You left the circle.", "Siz doiradan chiqdingiz."),
    # details
    "compat": ("Compatibility", "Moslik"),
    "cat_personality": ("Personality", "Xarakter"),
    "cat_interests": ("Common interests", "Umumiy qiziqishlar"),
    "cat_trust": ("Trust", "Ishonch"),
    "cat_communication": ("Communication", "Muloqot"),
    "cat_fun": ("Fun together", "Birga qiziqarli"),
    "common_hobbies": ("Common hobbies: {h}", "Umumiy hobbilar: {h}"),
    "contact_line": ("📞 Contact: {c}", "📞 Kontakt: {c}"),
    "expl_strong": ("I would give this friendship {pct}% because {strong}.",
                    "Men bu do'stlikni {pct}% deb baholayman, chunki {strong}."),
    "expl_weak": ("However, they may sometimes have problems because {weak}.",
                  "Biroq ba'zan muammolar chiqishi mumkin, chunki {weak}."),
    "expl_ok": ("However, every friendship needs effort, so they should keep talking honestly.",
                "Biroq har bir do'stlik harakat talab qiladi, shuning uchun ular ochiq gaplashib turishi kerak."),
    # friend requests
    "toast_sent": ("Request sent ✅", "So'rov yuborildi ✅"),
    "toast_pending": ("You already sent a request ⏳", "So'rovni allaqachon yuborgansiz ⏳"),
    "toast_friends": ("You are already friends 🤝", "Siz allaqachon do'stsiz 🤝"),
    "toast_connected": ("You are connected! 🎉", "Siz bog'landingiz! 🎉"),
    "req_incoming": (
        "🤝 <b>{name}</b> wants to be your friend!\nCompatibility: <b>{pct}%</b>\n\n{card}\n\n"
        "If you accept, you will share your Telegram contacts.",
        "🤝 <b>{name}</b> siz bilan do'st bo'lmoqchi!\nMoslik: <b>{pct}%</b>\n\n{card}\n\n"
        "Qabul qilsangiz, Telegram kontaktlaringiz bir-biringizga ko'rsatiladi.",
    ),
    "req_accepted": ("🎉 You are now connected with <b>{name}</b>!\nContact: {c}",
                     "🎉 Siz <b>{name}</b> bilan bog'landingiz!\nKontakt: {c}"),
    "req_declined": ("Request declined.", "So'rov rad etildi."),
    "req_gone": ("This request is no longer available.", "Bu so'rov endi mavjud emas."),
    "friends_title": ("🤝 <b>My friends</b>", "🤝 <b>Mening do'stlarim</b>"),
    "friends_none": ("No friends yet. Send a friend request from the Global list or from a circle!",
                     "Hozircha do'stlar yo'q. Global ro'yxat yoki doiradan do'stlik so'rovi yuboring!"),
    # misc
    "cancelled": ("Cancelled ✅", "Bekor qilindi ✅"),
    "unknown": ("I didn't understand 🤔 Use the buttons or /menu.",
                "Tushunmadim 🤔 Tugmalardan yoki /menu dan foydalaning."),
    "error": ("Something went wrong. Please try /menu.",
              "Nimadir xato ketdi. Iltimos, /menu ni sinab ko'ring."),
    "help_head": ("❓ <b>Help</b>\nAll commands are also in the ☰ Menu panel:",
                  "❓ <b>Yordam</b>\nBarcha buyruqlar ☰ Menu panelida ham bor:"),
    "project": (
        "📋 <b>Project checklist — Design the Perfect Friend</b>\n\n"
        "<b>Stage 1.</b> Create your teenager: name, age, 5–6 adjectives, strengths and weaknesses, "
        "hobbies, things they enjoy and dislike.\n"
        "<b>Stage 2.</b> Ideal best friend: 5 qualities + 2 qualities they should NOT have, common "
        "interests, activities together. Explain your choices with <i>because</i>!\n"
        "<b>Stage 3.</b> Friendship Compatibility Test: 5 original questions with possible answers.\n"
        "<b>Stage 4.</b> Friendship score: 5 categories out of 10, total out of 50 + explanation.\n\n"
        "<b>Language:</b> 8+ adjectives, 3+ with un-/in-/dis-, and -ing forms "
        "(enjoy spending, love meeting, avoid arguing...).\n"
        "<b>Team:</b> 3–4 students.  <b>Product:</b> poster, infographic, 4–5 slides or oral presentation.\n"
        "<b>Marks (25):</b> content, language, creativity, organisation, teamwork (5 each).",
        "📋 <b>Loyiha ro'yxati — Design the Perfect Friend</b>\n\n"
        "<b>1-bosqich.</b> Personaj yarating: ism, yosh, 5–6 ta sifat, kuchli va zaif tomonlar, "
        "hobbilar, nimani yoqtiradi va yoqtirmaydi.\n"
        "<b>2-bosqich.</b> Ideal do'st: 5 ta sifat + bo'lmasligi kerak 2 ta sifat, umumiy "
        "qiziqishlar, birga qiladigan ishlar. Tanlovingizni <i>because</i> bilan tushuntiring!\n"
        "<b>3-bosqich.</b> Friendship Compatibility Test: 5 ta original savol va javob variantlari.\n"
        "<b>4-bosqich.</b> Do'stlik bali: 5 ta kategoriya 10 balldan, jami 50 ball + izoh.\n\n"
        "<b>Til:</b> 8+ sifat, kamida 3 tasi un-/in-/dis- bilan, hamda -ing shakllari "
        "(enjoy spending, love meeting, avoid arguing...).\n"
        "<b>Jamoa:</b> 3–4 o'quvchi.  <b>Mahsulot:</b> poster, infografika, 4–5 slayd yoki og'zaki taqdimot.\n"
        "<b>Ball (25):</b> mazmun, til, ijodkorlik, tashkil etish, jamoaviy ish (har biri 5).",
    ),
}


def tx(key, lang, **kw):
    s = pick(T[key], lang)
    return s.format(**kw) if kw else s


def L(context):
    return context.user_data.get("lang", "uz")


# ══════════════════════════════════════════════════════════════════════════════
#  KEYBOARDS & MESSAGE HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def btn(text, data):
    return InlineKeyboardButton(text, callback_data=data)


def menu_keyboard(lang):
    b = lambda key, cb: btn(tx(key, lang), cb)  # noqa: E731
    return InlineKeyboardMarkup([
        [b("btn_profile", "menu:profile"), b("btn_test", "menu:test")],
        [b("btn_match", "menu:match"), b("btn_circles", "menu:circles")],
        [b("btn_friends", "menu:friends"), b("btn_project", "menu:project")],
        [b("btn_tip", "menu:tip"), b("btn_lang", "menu:language")],
        [b("btn_help", "menu:help")],
    ])


def only_menu_keyboard(lang):
    return InlineKeyboardMarkup([[btn(tx("btn_menu", lang), "menu:main")]])


async def send(update: Update, text, markup=None):
    await update.effective_message.reply_text(
        text, reply_markup=markup, parse_mode=ParseMode.HTML
    )


async def edit(update: Update, text, markup=None):
    try:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def edit_markup(update: Update, markup):
    try:
        await update.callback_query.edit_message_reply_markup(reply_markup=markup)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def notify(context, uid, text, markup=None):
    """Send a message to another user (fails silently if they blocked the bot)."""
    try:
        await context.bot.send_message(uid, text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not notify %s: %s", uid, e)


def need_profile_message(lang):
    markup = InlineKeyboardMarkup([
        [btn(tx("btn_profile", lang), "menu:profile")],
        [btn(tx("btn_menu", lang), "menu:main")],
    ])
    return tx("need_profile", lang), markup


# ══════════════════════════════════════════════════════════════════════════════
#  START / MENU / LANGUAGE / SMALL COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    u = update.effective_user
    touch_user(u.id, username=u.username)
    if "lang" not in context.user_data:
        await language_cmd(update, context)
        return
    lang = L(context)
    await send(update, tx("welcome", lang), menu_keyboard(lang))


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    lang = L(context)
    await send(update, tx("menu_title", lang), menu_keyboard(lang))


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    markup = InlineKeyboardMarkup([[btn("🇺🇿 O'zbekcha", "lang:uz"), btn("🇬🇧 English", "lang:en")]])
    await send(update, tx("choose_lang", "en"), markup)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    i = 0 if lang == "en" else 1
    lines = [tx("help_head", lang), ""]
    lines += [f"/{c} — {d[i]}" for c, d in COMMANDS]
    await send(update, "\n".join(lines), only_menu_keyboard(lang))


async def project_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    await send(update, tx("project", lang), only_menu_keyboard(lang))


async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    markup = InlineKeyboardMarkup([[btn("💡", "menu:tip"), btn(tx("btn_menu", lang), "menu:main")]])
    await send(update, "💡 " + pick(random.choice(TIPS), lang), markup)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    for k in ("draft", "test_progress"):
        context.user_data.pop(k, None)
    context.user_data["state"] = None
    context.user_data["reg"] = False
    await send(update, tx("cancelled", lang), menu_keyboard(lang))


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTRATION WIZARD  (name → age → traits → hobbies → wants → avoid → test → circle)
# ══════════════════════════════════════════════════════════════════════════════
FIELD_ORDER = ["traits", "hobbies", "wants", "avoid"]
LIMITS = {"traits": (3, 6), "hobbies": (1, 5), "wants": (3, 5), "avoid": (1, 2)}


def options_for(field):
    if field == "traits":
        return list(TRAITS)
    if field == "hobbies":
        return list(HOBBIES)
    if field == "wants":
        return [k for k, v in TRAITS.items() if v[2]]
    return [k for k, v in TRAITS.items() if not v[2]]  # "avoid"


def label_for(field, key, lang):
    return hobby_label(key, lang) if field == "hobbies" else trait_label(key, lang)


def select_keyboard(field, chosen, lang):
    rows, row = [], []
    for key in options_for(field):
        mark = "✅ " if key in chosen else ""
        row.append(btn(mark + label_for(field, key, lang), f"sel:{field}:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    mx = LIMITS[field][1]
    rows.append([btn(f"{tx('btn_done', lang)} ({len(chosen)}/{mx})", f"done:{field}")])
    return InlineKeyboardMarkup(rows)


async def send_field(update, context, field, edit_msg=False):
    lang = L(context)
    chosen = context.user_data["draft"].setdefault(field, [])
    mn, mx = LIMITS[field]
    text = tx("ask_" + field, lang, mn=mn, mx=mx)
    markup = select_keyboard(field, chosen, lang)
    if edit_msg:
        await edit(update, text, markup)
    else:
        await send(update, text, markup)


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"] = {}
    context.user_data["state"] = "name"
    context.user_data["reg"] = False
    await send(update, tx("ask_name", L(context)))


def profile_card(p, lang, show_age=False, show_wants=False):
    lines = [f"👤 <b>{esc(p['name'])}</b>" + (f", {p['age']}" if show_age and p.get("age") else ""), ""]
    lines.append(f"🧩 <b>{tx('lbl_traits', lang)}:</b> {', '.join(trait_label(k, lang) for k in p['traits'])}")
    lines.append(f"🎯 <b>{tx('lbl_hobbies', lang)}:</b> {', '.join(hobby_label(k, lang) for k in p['hobbies'])}")
    if show_wants:
        lines.append(f"💖 <b>{tx('lbl_wants', lang)}:</b> {', '.join(trait_label(k, lang) for k in p['wants'])}")
        lines.append(f"🚫 <b>{tx('lbl_avoid', lang)}:</b> {', '.join(trait_label(k, lang) for k in p['avoid'])}")
    return "\n".join(lines)


def own_profile_view(me, lang):
    text = profile_card(me, lang, show_age=True, show_wants=True)
    text += "\n\n" + tx("vis_on" if me["visible"] else "vis_off", lang)
    vis_btn = btn(tx("btn_vis_hide" if me["visible"] else "btn_vis_show", lang), "prof:vis")
    markup = InlineKeyboardMarkup([
        [btn(tx("btn_redo", lang), "prof:redo"), btn(tx("btn_test", lang), "menu:test")],
        [vis_btn],
        [btn(tx("btn_menu", lang), "menu:main")],
    ])
    return text, markup


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = get_user(update.effective_user.id)
    if me is None:
        await start_registration(update, context)
    else:
        text, markup = own_profile_view(me, L(context))
        await send(update, text, markup)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY TEST
# ══════════════════════════════════════════════════════════════════════════════
def question_text(i, lang):
    q = QUESTIONS[i]
    lines = [tx("test_title", lang, i=i + 1, n=len(QUESTIONS)), "", f"<b>{pick(q['q'], lang)}</b>", ""]
    for letter, opt in zip("ABC", q["opts"]):
        lines.append(f"<b>{letter})</b> {pick(opt, lang)}")
    return "\n".join(lines)


def question_keyboard(i):
    return InlineKeyboardMarkup([[btn(letter, f"ans:{i}:{j}") for j, letter in enumerate("ABC")]])


async def begin_test(update, context):
    context.user_data["state"] = None
    context.user_data["test_progress"] = []
    await send(update, question_text(0, L(context)), question_keyboard(0))


async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retake the test (only for registered users)."""
    if get_user(update.effective_user.id) is None:
        text, markup = need_profile_message(L(context))
        await send(update, text, markup)
        return
    context.user_data["reg"] = False
    await begin_test(update, context)


# ══════════════════════════════════════════════════════════════════════════════
#  RANKINGS  (global + circles) and detail view
# ══════════════════════════════════════════════════════════════════════════════
def ranking_view(me, others, lang, header, empty, src, top, bottom_rows):
    scored = sorted(((pair_score(me, o), o) for o in others),
                    key=lambda x: x[0]["total"], reverse=True)[:top]
    lines = [header, ""]
    rows, row = [], []
    if not scored:
        lines.append(empty)
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 50
    for m, (s, o) in zip(medals, scored):
        lines.append(f"{m} <b>{esc(o['name'])}</b> — {s['pct']}% · {rating(s['pct'], lang)}")
        row.append(btn(f"{o['name']} ({s['pct']}%)", f"det:{o['id']}:{src}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows += bottom_rows
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def global_view(me, lang):
    header = tx("global_title", lang, n=GLOBAL_TOP)
    bottom = [[btn(tx("btn_menu", lang), "menu:main")]]
    return ranking_view(me, global_others(me["id"]), lang, header, tx("no_users", lang), "g", GLOBAL_TOP, bottom)


def circle_view(me, cid, lang):
    c = get_circle(cid)
    header = tx("circle_header", lang, name=esc(c["name"]), n=count_members(cid), code=c["code"])
    bottom = [
        [btn(tx("btn_leave", lang), f"cl:{cid}")],
        [btn(tx("btn_circles_back", lang), "menu:circles"), btn(tx("btn_menu", lang), "menu:main")],
    ]
    return ranking_view(me, circle_others(cid, me["id"]), lang, header, tx("circle_alone", lang),
                        f"c{cid}", CIRCLE_TOP, bottom)


def detail_view(me, other, src, lang):
    s = pair_score(me, other)
    lines = [f"💞 <b>{esc(me['name'])} ❤️ {esc(other['name'])}</b>", "",
             profile_card(other, lang), ""]
    for cat in CATS:
        lines.append(f"{tx('cat_' + cat, lang)}: <b>{s[cat] * 10}%</b>\n<code>{bar(s[cat])}</code>")
    lines.append(f"\n<b>{tx('compat', lang)}: {s['pct']}%</b> — {rating(s['pct'], lang)}")
    if s["common"]:
        lines.append(tx("common_hobbies", lang, h=", ".join(hobby_label(h, lang) for h in s["common"])))

    ranked = sorted(CATS, key=lambda c: s[c])  # ascending, stable
    worst, best = ranked[0], ranked[-1]
    if best == "interests" and not s["common"]:
        best = ranked[-2]
    strong = pick(STRONG[best], lang)
    if best == "interests":
        strong = strong.format(hobbies=", ".join(HOBBIES[h][1] for h in s["common"]))
    lines.append("")
    lines.append(tx("expl_strong", lang, pct=s["pct"], strong=strong))
    lines.append(tx("expl_ok", lang) if s[worst] >= 8 else tx("expl_weak", lang, weak=pick(WEAK[worst], lang)))

    st = req_status(me["id"], other["id"])
    if st == "friends":
        lines.append("\n" + tx("contact_line", lang, c=contact(other)))
        action = btn(tx("btn_friends_already", lang), "noop")
    elif st == "sent":
        action = btn(tx("btn_req_sent", lang), "noop")
    elif st == "received":
        action = btn(tx("btn_accept_their", lang), f"fr:{other['id']}:{src}")
    else:
        action = btn(tx("btn_send_req", lang), f"fr:{other['id']}:{src}")
    markup = InlineKeyboardMarkup([
        [action],
        [btn(tx("btn_back", lang), f"rank:{src}")],
        [btn(tx("btn_menu", lang), "menu:main")],
    ])
    return "\n".join(lines), markup


async def match_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    me = get_user(update.effective_user.id)
    if me is None:
        text, markup = need_profile_message(lang)
    else:
        text, markup = global_view(me, lang)
    await send(update, text, markup)


# ══════════════════════════════════════════════════════════════════════════════
#  CIRCLES
# ══════════════════════════════════════════════════════════════════════════════
def circles_view(uid, lang):
    cs = my_circles(uid)
    lines = [tx("circles_title", lang), ""]
    rows = []
    if not cs:
        lines.append(tx("circles_none", lang))
    for c in cs:
        rows.append([btn(f"🔵 {c['name']} ({count_members(c['id'])})", f"cv:{c['id']}")])
    rows.append([btn(tx("btn_circ_new", lang), "circ:new"), btn(tx("btn_circ_join", lang), "circ:join")])
    rows.append([btn(tx("btn_menu", lang), "menu:main")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def circles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    uid = update.effective_user.id
    if get_user(uid) is None:
        text, markup = need_profile_message(lang)
    else:
        text, markup = circles_view(uid, lang)
    await send(update, text, markup)


async def friends_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    me = get_user(update.effective_user.id)
    if me is None:
        text, markup = need_profile_message(lang)
        await send(update, text, markup)
        return
    fr = friends_of(me["id"])
    lines = [tx("friends_title", lang), ""]
    if not fr:
        lines.append(tx("friends_none", lang))
    for f in fr:
        lines.append(f"• <b>{esc(f['name'])}</b> — {contact(f)} · {pair_score(me, f)['pct']}%")
    await send(update, "\n".join(lines), only_menu_keyboard(lang))


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT MESSAGES (wizard: name, age; circles: name, code)
# ══════════════════════════════════════════════════════════════════════════════
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    ud = context.user_data
    state = ud.get("state")
    draft = ud.get("draft")
    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    if state == "name" and draft is not None:
        if not 2 <= len(text) <= 20:
            await send(update, tx("bad_name", lang))
            return
        draft["name"] = text
        ud["state"] = "age"
        await send(update, tx("ask_age", lang))

    elif state == "age" and draft is not None:
        if not text.isdigit() or not 10 <= int(text) <= 25:
            await send(update, tx("bad_age", lang))
            return
        draft["age"] = int(text)
        ud["state"] = None
        await send_field(update, context, "traits")

    elif state == "circle_name":
        if not 2 <= len(text) <= 25:
            await send(update, tx("bad_circle_name", lang))
            return
        if len(my_circles(uid)) >= MAX_CIRCLES:
            ud["state"] = None
            await send(update, tx("max_circles", lang, n=MAX_CIRCLES), only_menu_keyboard(lang))
            return
        cid, code = create_circle(uid, text)
        ud["state"] = None
        markup = InlineKeyboardMarkup([
            [btn(tx("btn_view_circle", lang), f"cv:{cid}")],
            [btn(tx("btn_menu", lang), "menu:main")],
        ])
        await send(update, tx("circle_created", lang, name=esc(text), code=code), markup)

    elif state == "circle_code":
        c = find_circle_by_code(text.upper().replace(" ", ""))
        if c is None:
            await send(update, tx("bad_code", lang))
            return
        ud["state"] = None
        if is_member(c["id"], uid):
            await send(update, tx("already_member", lang), only_menu_keyboard(lang))
            return
        if len(my_circles(uid)) >= MAX_CIRCLES:
            await send(update, tx("max_circles", lang, n=MAX_CIRCLES), only_menu_keyboard(lang))
            return
        join_circle(c["id"], uid)
        markup = InlineKeyboardMarkup([
            [btn(tx("btn_view_circle", lang), f"cv:{c['id']}")],
            [btn(tx("btn_menu", lang), "menu:main")],
        ])
        await send(update, tx("circle_joined", lang, name=esc(c["name"])), markup)

    else:
        await send(update, tx("unknown", lang), menu_keyboard(lang))


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════════════════════
MENU_ACTIONS = {
    "main": menu_cmd, "profile": profile_cmd, "test": test_cmd, "match": match_cmd,
    "circles": circles_cmd, "friends": friends_cmd, "project": project_cmd,
    "tip": tip_cmd, "language": language_cmd, "help": help_cmd,
}


def parse_src(src):
    """'g' → global, 'c12' → circle 12."""
    if src == "g":
        return "g", None
    if src.startswith("c") and src[1:].isdigit():
        return "c", int(src[1:])
    return None, None


async def show_rank(update, context, me, src, lang):
    kind, cid = parse_src(src)
    if kind == "g":
        text, markup = global_view(me, lang)
    elif kind == "c" and get_circle(cid) and is_member(cid, me["id"]):
        text, markup = circle_view(me, cid, lang)
    else:
        text, markup = circles_view(me["id"], lang)
    await edit(update, text, markup)


async def finalize_friendship(context, requester_id, acceptor_id):
    """Mark as accepted and send the acceptor's contact to the requester."""
    set_request(requester_id, acceptor_id, "accepted")
    requester, acceptor = get_user(requester_id), get_user(acceptor_id)
    if requester and acceptor:
        await notify(context, requester_id,
                     tx("req_accepted", requester["lang"], name=esc(acceptor["name"]), c=contact(acceptor)))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    lang = L(context)
    uid = update.effective_user.id
    touch_user(uid, username=update.effective_user.username)
    kind, _, rest = (q.data or "").partition(":")

    # ---- language ----------------------------------------------------------
    if kind == "lang":
        new = rest if rest in ("uz", "en") else "uz"
        context.user_data["lang"] = new
        touch_user(uid, lang=new)
        await q.answer()
        try:  # make the command panel match the chosen language for this chat
            await context.bot.set_my_commands(
                commands_for(new), scope=BotCommandScopeChat(update.effective_chat.id)
            )
        except Exception as e:  # noqa: BLE001
            log.warning("set_my_commands failed: %s", e)
        await edit(update, tx("welcome", new), menu_keyboard(new))

    # ---- main menu buttons -------------------------------------------------
    elif kind == "menu":
        await q.answer()
        action = MENU_ACTIONS.get(rest)
        if action:
            await action(update, context)

    # ---- own profile actions ---------------------------------------------------
    elif kind == "prof":
        await q.answer()
        me = get_user(uid)
        if rest == "redo":
            await start_registration(update, context)
        elif rest == "vis" and me:
            set_visible(uid, not me["visible"])
            text, markup = own_profile_view(get_user(uid), lang)
            await edit(update, text, markup)

    # ---- wizard selections -----------------------------------------------------
    elif kind == "sel":
        field, _, key = rest.partition(":")
        draft = context.user_data.get("draft")
        if draft is None or field not in LIMITS or key not in options_for(field):
            await q.answer(tx("stale", lang), show_alert=True)
            return
        chosen = draft.setdefault(field, [])
        if key in chosen:
            chosen.remove(key)
        else:
            if len(chosen) >= LIMITS[field][1]:
                await q.answer(tx("limit_reached", lang, mx=LIMITS[field][1]), show_alert=True)
                return
            chosen.append(key)
        await q.answer()
        await edit_markup(update, select_keyboard(field, chosen, lang))

    elif kind == "done":
        field = rest
        draft = context.user_data.get("draft")
        if draft is None or field not in LIMITS:
            await q.answer(tx("stale", lang), show_alert=True)
            return
        mn, _mx = LIMITS[field]
        if len(draft.get(field, [])) < mn:
            await q.answer(tx("need_min", lang, mn=mn), show_alert=True)
            return
        await q.answer()
        idx = FIELD_ORDER.index(field)
        if idx + 1 < len(FIELD_ORDER):
            await send_field(update, context, FIELD_ORDER[idx + 1], edit_msg=True)
        else:
            card = profile_card(draft, lang, show_age=True, show_wants=True)
            await edit(update, tx("prof_ready", lang, card=card))
            context.user_data["reg"] = True
            await begin_test(update, context)

    # ---- test answers ------------------------------------------------------------
    elif kind == "ans":
        try:
            i, j = (int(x) for x in rest.split(":"))
        except ValueError:
            await q.answer()
            return
        prog = context.user_data.get("test_progress")
        if prog is None or len(prog) != i or not 0 <= j <= 2:
            await q.answer(tx("stale", lang), show_alert=True)
            return
        prog.append(j)
        await q.answer()
        if i + 1 < len(QUESTIONS):
            await edit(update, question_text(i + 1, lang), question_keyboard(i + 1))
            return
        answers = list(prog)
        context.user_data["test_progress"] = None
        draft = context.user_data.get("draft")
        if context.user_data.get("reg") and draft and all(k in draft for k in ("name", "age", *FIELD_ORDER)):
            save_user(uid, update.effective_user.username, draft, answers, lang)
            context.user_data.pop("draft", None)
            context.user_data["reg"] = False
            markup = InlineKeyboardMarkup([
                [btn(tx("btn_show_global", lang), "rank:g")],
                [btn(tx("btn_circ_new", lang), "circ:new"), btn(tx("btn_circ_join", lang), "circ:join")],
                [btn(tx("btn_skip", lang), "menu:main")],
            ])
            await edit(update, tx("reg_done", lang), markup)
        elif get_user(uid):
            update_answers(uid, answers)
            markup = InlineKeyboardMarkup([
                [btn(tx("btn_show_global", lang), "rank:g")],
                [btn(tx("btn_menu", lang), "menu:main")],
            ])
            await edit(update, tx("test_updated", lang), markup)
        else:
            await edit(update, tx("stale", lang), menu_keyboard(lang))

    # ---- rankings & details ------------------------------------------------------
    elif kind == "rank":
        await q.answer()
        me = get_user(uid)
        if me is None:
            text, markup = need_profile_message(lang)
            await edit(update, text, markup)
            return
        await show_rank(update, context, me, rest, lang)

    elif kind == "cv":
        me = get_user(uid)
        try:
            cid = int(rest)
        except ValueError:
            await q.answer()
            return
        if me is None or not get_circle(cid) or not is_member(cid, uid):
            await q.answer(tx("stale", lang), show_alert=True)
            return
        await q.answer()
        text, markup = circle_view(me, cid, lang)
        await edit(update, text, markup)

    elif kind == "det":
        oid_s, _, src = rest.partition(":")
        me = get_user(uid)
        other = get_user(int(oid_s)) if oid_s.isdigit() else None
        if me is None or other is None or other["id"] == uid:
            await q.answer(tx("stale", lang), show_alert=True)
            return
        await q.answer()
        text, markup = detail_view(me, other, src, lang)
        await edit(update, text, markup)

    # ---- friend requests ---------------------------------------------------------
    elif kind == "fr":
        oid_s, _, src = rest.partition(":")
        me = get_user(uid)
        other = get_user(int(oid_s)) if oid_s.isdigit() else None
        if me is None or other is None or other["id"] == uid:
            await q.answer(tx("stale", lang), show_alert=True)
            return
        st = req_status(uid, other["id"])
        if st == "friends":
            await q.answer(tx("toast_friends", lang))
        elif st == "sent":
            await q.answer(tx("toast_pending", lang))
        elif st == "received":
            await q.answer(tx("toast_connected", lang))
            await finalize_friendship(context, other["id"], uid)
        else:
            add_request(uid, other["id"])
            await q.answer(tx("toast_sent", lang))
            olang = other["lang"]
            pct = pair_score(me, other)["pct"]
            markup = InlineKeyboardMarkup([[
                btn(tx("btn_accept", olang), f"req:acc:{uid}"),
                btn(tx("btn_decline", olang), f"req:dec:{uid}"),
            ]])
            await notify(context, other["id"],
                         tx("req_incoming", olang, name=esc(me["name"]), pct=pct,
                            card=profile_card(me, olang)), markup)
        text, markup = detail_view(me, other, src, lang)
        await edit(update, text, markup)

    elif kind == "req":
        action, _, fid_s = rest.partition(":")
        fid = int(fid_s) if fid_s.isdigit() else 0
        row = db.execute("SELECT status FROM requests WHERE from_id=? AND to_id=?", (fid, uid)).fetchone()
        await q.answer()
        other = get_user(fid)
        if row is None or row["status"] != "pending" or other is None:
            await edit(update, tx("req_gone", lang))
            return
        if action == "acc":
            await finalize_friendship(context, fid, uid)
            await edit(update, tx("req_accepted", lang, name=esc(other["name"]), c=contact(other)))
        else:
            set_request(fid, uid, "declined")
            await edit(update, tx("req_declined", lang))

    # ---- circles ------------------------------------------------------------------
    elif kind == "circ":
        await q.answer()
        if get_user(uid) is None:
            text, markup = need_profile_message(lang)
            await send(update, text, markup)
            return
        if rest == "new":
            context.user_data["state"] = "circle_name"
            await send(update, tx("ask_circle_name", lang))
        elif rest == "join":
            context.user_data["state"] = "circle_code"
            await send(update, tx("ask_circle_code", lang))

    elif kind == "cl":  # leave: ask for confirmation
        try:
            cid = int(rest)
        except ValueError:
            await q.answer()
            return
        c = get_circle(cid)
        if c is None or not is_member(cid, uid):
            await q.answer(tx("stale", lang), show_alert=True)
            return
        await q.answer()
        markup = InlineKeyboardMarkup([[btn(tx("btn_yes", lang), f"cly:{cid}"),
                                        btn(tx("btn_no", lang), f"cv:{cid}")]])
        await edit(update, tx("leave_confirm", lang, name=esc(c["name"])), markup)

    elif kind == "cly":  # leave: confirmed
        try:
            cid = int(rest)
        except ValueError:
            await q.answer()
            return
        await q.answer()
        if get_circle(cid) and is_member(cid, uid):
            leave_circle(cid, uid)
        text, markup = circles_view(uid, lang)
        await edit(update, tx("left", lang) + "\n\n" + text, markup)

    else:  # "noop" and anything unknown
        await q.answer()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            lang = context.user_data.get("lang", "uz") if context.user_data is not None else "uz"
            await update.effective_message.reply_text(tx("error", lang))
        except Exception:  # noqa: BLE001
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    if not TOKEN:
        raise SystemExit("❌ Set your bot token: BOT_TOKEN=... python friend_match_bot_v2.py "
                         "(get it from @BotFather). Never write it inside the code!")

    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    persistence = PicklePersistence(filepath=os.path.join(DATA_DIR, "friend_match_state.pkl"))
    app = Application.builder().token(TOKEN).persistence(persistence).post_init(post_init).build()

    for name, handler in [
        ("start", start), ("menu", menu_cmd), ("profile", profile_cmd), ("test", test_cmd),
        ("match", match_cmd), ("circles", circles_cmd), ("friends", friends_cmd),
        ("project", project_cmd), ("tip", tip_cmd), ("language", language_cmd),
        ("help", help_cmd), ("cancel", cancel_cmd),
    ]:
        app.add_handler(CommandHandler(name, handler))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(error_handler)

    log.info("Bot is running... press Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
