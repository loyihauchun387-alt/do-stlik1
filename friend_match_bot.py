#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💞 Friend Match Bot  |  Do'stlik boti
=====================================
Project: "Design the Perfect Friend" (Unit 1-2)

Features / Imkoniyatlar
- 🌐 Two languages: Uzbek and English (switch any time with /language)
- ☰  Command panel (the Menu button next to the message box) + inline main menu
- 👤 /profile  - create your own profile (name, age, adjectives, hobbies, wanted / unwanted qualities)
- 🧪 /test     - 5-question Friendship Compatibility Test
- 💞 /match    - matches you with 8 fictional teenagers, score out of 50
- 👥 /users    - browse the fictional teenagers (cards with strengths, weaknesses, likes, dislikes)
- 📋 /project  - checklist of the project requirements
- 🔤 /words    - prefix adjectives (un-, in-, dis-) and verb + -ing list
- 💡 /tip      - random friendship tip

Install:   pip install "python-telegram-bot>=21"
Run:       BOT_TOKEN=123456:ABC... python friend_match_bot.py
           (or paste the token into TOKEN below)
"""

import html
import logging
import os
import random

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

TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")

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
    # negative traits (three of them have un- / in- / dis- prefixes!)
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
#  FICTIONAL TEENAGERS   (edit / add your own here!)
#  answers = their answer (0, 1 or 2) to each of the 5 test questions
# ══════════════════════════════════════════════════════════════════════════════
FAKE_USERS = [
    {
        "id": "amelia", "name": "Amelia", "age": 15, "emoji": "🎨",
        "traits": ["outgoing", "imaginative", "curious", "energetic", "impatient", "disorganized"],
        "hobbies": ["painting", "travel", "hiking"],
        "answers": [1, 2, 2, 1, 2],
        "strength": ("She makes friends easily and has wonderful ideas.",
                     "U tez do'st orttiradi va ajoyib g'oyalari bor."),
        "weakness": ("She can be impatient and sometimes forgets her homework.",
                     "U ba'zan sabrsiz bo'ladi va uy vazifasini unutib qo'yadi."),
        "likes": ("enjoys meeting new people and trying unusual activities",
                  "yangi odamlar bilan tanishishni va g'alati mashg'ulotlarni sinashni yoqtiradi"),
        "dislikes": ("dislikes spending too much time online",
                     "internetda ko'p vaqt o'tkazishni yoqtirmaydi"),
    },
    {
        "id": "aziza", "name": "Aziza", "age": 16, "emoji": "📚",
        "traits": ["patient", "calm", "honest", "loyal", "kind", "disorganized"],
        "hobbies": ["reading", "chess", "music"],
        "answers": [0, 1, 1, 0, 0],
        "strength": ("She is a great listener and keeps every secret.",
                     "U yaxshi tinglovchi va har bir sirni saqlaydi."),
        "weakness": ("Her desk is always disorganized and she is late sometimes.",
                     "Uning stoli doim tartibsiz va ba'zan kechikadi."),
        "likes": ("loves reading fantasy novels and enjoys talking about books",
                  "fantastik romanlarni o'qishni yaxshi ko'radi va kitoblar haqida gaplashishni yoqtiradi"),
        "dislikes": ("dislikes shouting and can't stand arguing",
                     "baqirishni yoqtirmaydi va tortishuvlarga chidolmaydi"),
    },
    {
        "id": "jasur", "name": "Jasur", "age": 16, "emoji": "⚽",
        "traits": ["energetic", "funny", "loyal", "outgoing", "impatient", "insensitive"],
        "hobbies": ["football", "swimming", "gaming"],
        "answers": [2, 1, 2, 1, 2],
        "strength": ("He is the funniest person in class and never gives up.",
                     "U sinfdagi eng kulgili odam va hech qachon taslim bo'lmaydi."),
        "weakness": ("He is sometimes insensitive and speaks before thinking.",
                     "U ba'zan his-tuyg'usiz bo'ladi va o'ylamasdan gapiradi."),
        "likes": ("enjoys playing football and prefers being outdoors",
                  "futbol o'ynashni yoqtiradi va ochiq havoda bo'lishni afzal ko'radi"),
        "dislikes": ("hates waiting and doesn't like sitting still",
                     "kutishni yomon ko'radi va bir joyda o'tirishni yoqtirmaydi"),
    },
    {
        "id": "madina", "name": "Madina", "age": 15, "emoji": "🎵",
        "traits": ["creative", "kind", "imaginative", "calm", "curious", "unreliable"],
        "hobbies": ["music", "dancing", "photography"],
        "answers": [0, 0, 1, 1, 1],
        "strength": ("She writes beautiful songs and cheers everyone up.",
                     "U chiroyli qo'shiqlar yozadi va hammaning kayfiyatini ko'taradi."),
        "weakness": ("She can be unreliable and often forgets to reply to messages.",
                     "U ba'zan ishonchsiz bo'ladi va xabarlarga javob berishni ko'pincha unutadi."),
        "likes": ("loves singing and enjoys taking photos of everyday life",
                  "qo'shiq aytishni yaxshi ko'radi va kundalik hayot suratlarini olishni yoqtiradi"),
        "dislikes": ("dislikes being the centre of attention and avoids arguing",
                     "e'tibor markazida bo'lishni yoqtirmaydi va tortishishdan qochadi"),
    },
    {
        "id": "daniel", "name": "Daniel", "age": 17, "emoji": "💻",
        "traits": ["curious", "organized", "honest", "patient", "calm", "unfriendly"],
        "hobbies": ["coding", "chess", "gaming"],
        "answers": [1, 2, 1, 2, 0],
        "strength": ("He solves problems logically and always keeps his word.",
                     "U muammolarni mantiqiy hal qiladi va so'zida turadi."),
        "weakness": ("He seems unfriendly at first because he is quiet with strangers.",
                     "U notanishlar bilan jim bo'lgani uchun avvaliga sovuqmuomala tuyuladi."),
        "likes": ("enjoys building apps and prefers working on projects alone",
                  "ilovalar yaratishni yoqtiradi va loyihalar ustida yolg'iz ishlashni afzal ko'radi"),
        "dislikes": ("dislikes noisy places and can't stand being late",
                     "shovqinli joylarni yoqtirmaydi va kechikishga chidolmaydi"),
    },
    {
        "id": "sardor", "name": "Sardor", "age": 15, "emoji": "🍳",
        "traits": ["funny", "kind", "loyal", "outgoing", "energetic", "disorganized"],
        "hobbies": ["cooking", "volunteering", "football"],
        "answers": [1, 1, 1, 1, 2],
        "strength": ("He is generous and always ready to help.",
                     "U saxiy va doim yordam berishga tayyor."),
        "weakness": ("He is disorganized and often loses his things.",
                     "U tartibsiz va ko'pincha narsalarini yo'qotib qo'yadi."),
        "likes": ("loves cooking for friends and doesn't mind helping others",
                  "do'stlari uchun ovqat pishirishni yaxshi ko'radi va boshqalarga yordam berishdan qaytmaydi"),
        "dislikes": ("dislikes gossiping and avoids being alone for long",
                     "g'iybatni yoqtirmaydi va uzoq yolg'iz qolishdan qochadi"),
    },
    {
        "id": "nilufar", "name": "Nilufar", "age": 16, "emoji": "📷",
        "traits": ["creative", "curious", "honest", "energetic", "imaginative", "insensitive"],
        "hobbies": ["photography", "travel", "volunteering"],
        "answers": [2, 2, 1, 2, 1],
        "strength": ("She always tells the truth and notices tiny details.",
                     "U doim rost gapiradi va mayda detallarni payqaydi."),
        "weakness": ("She can seem insensitive because she is very direct.",
                     "U juda to'g'ri gapirgani uchun ba'zan his-tuyg'usizdek tuyuladi."),
        "likes": ("enjoys travelling and loves taking photos of old buildings",
                  "sayohat qilishni yoqtiradi va qadimiy binolarni suratga olishni yaxshi ko'radi"),
        "dislikes": ("dislikes lying and can't stand unfair rules",
                     "yolg'on gapirishni yoqtirmaydi va adolatsiz qoidalarga chidolmaydi"),
    },
    {
        "id": "leo", "name": "Leo", "age": 17, "emoji": "♟️",
        "traits": ["calm", "patient", "loyal", "funny", "organized", "curious"],
        "hobbies": ["chess", "hiking", "music"],
        "answers": [1, 1, 1, 1, 1],
        "strength": ("He stays calm in every situation and gives good advice.",
                     "U har qanday vaziyatda xotirjam bo'ladi va yaxshi maslahat beradi."),
        "weakness": ("He can be stubborn and hates changing his plans.",
                     "U o'jar bo'lishi mumkin va rejalarini o'zgartirishni yomon ko'radi."),
        "likes": ("enjoys playing chess and loves walking in the mountains",
                  "shaxmat o'ynashni yoqtiradi va tog'larda sayr qilishni yaxshi ko'radi"),
        "dislikes": ("dislikes being rushed and prefers avoiding drama",
                     "shoshirilishni yoqtirmaydi va janjaldan qochishni afzal ko'radi"),
    },
]
FAKE_BY_ID = {f["id"]: f for f in FAKE_USERS}


# ══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY TEST  (edit these with your GROUP'S OWN questions for Stage 3!)
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
RATINGS = [
    (42, ("Perfect match ✨", "Ajoyib juftlik ✨")),
    (34, ("Great friends 😄", "Zo'r do'stlar 😄")),
    (26, ("Good potential 🙂", "Yaxshi imkoniyat 🙂")),
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
#  COMMAND PANEL
# ══════════════════════════════════════════════════════════════════════════════
COMMANDS = [
    ("start", ("Start the bot", "Botni ishga tushirish")),
    ("menu", ("Main menu", "Asosiy menyu")),
    ("profile", ("Create my profile", "Profilimni yaratish")),
    ("test", ("Friendship compatibility test", "Do'stlik mosligi testi")),
    ("match", ("Find my best friend match", "Eng mos do'stni topish")),
    ("users", ("Fictional teenagers", "Xayoliy o'smirlar")),
    ("project", ("Project checklist", "Loyiha ro'yxati")),
    ("words", ("Project vocabulary", "Loyiha lug'ati")),
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
        "I help teenagers find their perfect friend. You can:\n"
        "• create your profile,\n"
        "• take the friendship compatibility test,\n"
        "• get matched with fictional teenagers and see a score out of 50!\n\n"
        "Use the buttons below, or the <b>Menu</b> button (☰) next to the message box "
        "to open the command panel.",
        "👋 Salom! Men <b>Friend Match Bot</b>man 💞\n\n"
        "O'smirlarga eng mos do'st topishda yordam beraman. Siz:\n"
        "• o'z profilingizni yaratishingiz,\n"
        "• do'stlik mosligi testidan o'tishingiz,\n"
        "• xayoliy o'smirlar bilan moslikni 50 balldan ko'rishingiz mumkin!\n\n"
        "Quyidagi tugmalardan yoki xabar yozish maydoni yonidagi <b>Menu</b> (☰) "
        "tugmasidan (buyruqlar paneli) foydalaning.",
    ),
    "menu_title": ("🏠 <b>Main menu</b>\nChoose what you want to do:",
                   "🏠 <b>Asosiy menyu</b>\nNima qilmoqchisiz?"),
    # buttons
    "btn_profile": ("👤 My profile", "👤 Profilim"),
    "btn_test": ("🧪 Compatibility test", "🧪 Moslik testi"),
    "btn_match": ("💞 Find my match", "💞 Mos do'stni topish"),
    "btn_users": ("👥 Fictional users", "👥 Xayoliy o'smirlar"),
    "btn_project": ("📋 Project checklist", "📋 Loyiha ro'yxati"),
    "btn_words": ("🔤 Project words", "🔤 Loyiha lug'ati"),
    "btn_tip": ("💡 Friendship tip", "💡 Do'stlik maslahati"),
    "btn_lang": ("🌐 Language", "🌐 Til"),
    "btn_help": ("❓ Help", "❓ Yordam"),
    "btn_menu": ("🏠 Menu", "🏠 Menyu"),
    "btn_done": ("✅ Done", "✅ Tayyor"),
    "btn_score_me": ("💞 Score with me", "💞 Men bilan moslik"),
    "btn_card": ("👤 Profile card", "👤 Profil kartasi"),
    "btn_back_matches": ("⬅️ Back to matches", "⬅️ Natijalarga qaytish"),
    "btn_take_test": ("🧪 Take the test", "🧪 Testni boshlash"),
    "btn_make_profile": ("👤 Create profile", "👤 Profil yaratish"),
    "btn_show_match": ("💞 Show my matches", "💞 Natijalarni ko'rish"),
    "btn_another": ("💡 Another tip", "💡 Yana maslahat"),
    # profile wizard
    "ask_name": (
        "👤 <b>Step 1/6 — Name</b>\nWhat is your name? (You can also invent a character's name.)",
        "👤 <b>1/6-qadam — Ism</b>\nIsmingiz nima? (Xayoliy personaj ismini ham yozishingiz mumkin.)",
    ),
    "ask_age": ("🎂 <b>Step 2/6 — Age</b>\nHow old are you? (10–25)",
                "🎂 <b>2/6-qadam — Yosh</b>\nNecha yoshdasiz? (10–25)"),
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
    "stale": ("This button is old. Please start again with the menu.",
              "Bu tugma eskirgan. Menyu orqali qaytadan boshlang."),
    "profile_saved": ("✅ <b>Profile saved!</b>", "✅ <b>Profil saqlandi!</b>"),
    "next_test": ("Next: take the compatibility test 👇",
                  "Keyingi qadam: moslik testidan o'ting 👇"),
    "need_profile": ("First, create your profile 👇", "Avval profilingizni yarating 👇"),
    "need_test": ("First, take the compatibility test 👇", "Avval moslik testidan o'ting 👇"),
    # labels
    "lbl_traits": ("Personality", "Xarakter"),
    "lbl_hobbies": ("Hobbies", "Hobbilar"),
    "lbl_wants": ("Wants in a friend", "Do'stda kerak"),
    "lbl_avoid": ("Does not want", "Do'stda kerak emas"),
    "lbl_strength": ("Strength", "Kuchli tomoni"),
    "lbl_weakness": ("Weakness", "Zaif tomoni"),
    "lbl_likes": ("Likes", "Yoqtiradi"),
    "lbl_dislikes": ("Dislikes", "Yoqtirmaydi"),
    # test
    "test_title": ("🧪 <b>Friendship Compatibility Test</b> — question {i}/{n}",
                   "🧪 <b>Do'stlik mosligi testi</b> — {i}/{n}-savol"),
    "test_done": ("✅ <b>Test complete!</b>\nNow let's see who matches you best.",
                  "✅ <b>Test yakunlandi!</b>\nEndi sizga kim eng mos ekanini ko'ramiz."),
    # match
    "match_title": ("💞 <b>Your friend matches</b> (score out of 50)\nTap a name for details:",
                    "💞 <b>Sizga mos do'stlar</b> (50 balldan)\nBatafsil ma'lumot uchun ismni bosing:"),
    "cat_personality": ("Personality", "Xarakter"),
    "cat_interests": ("Common interests", "Umumiy qiziqishlar"),
    "cat_trust": ("Trust", "Ishonch"),
    "cat_communication": ("Communication", "Muloqot"),
    "cat_fun": ("Fun together", "Birga qiziqarli"),
    "total": ("TOTAL", "JAMI"),
    "common_hobbies": ("Common hobbies: {h}", "Umumiy hobbilar: {h}"),
    "expl_strong": ("I would give this friendship {total}/50 because {strong}.",
                    "Men bu do'stlikka {total}/50 ball beraman, chunki {strong}."),
    "expl_weak": ("However, they may sometimes have problems because {weak}.",
                  "Biroq ba'zan muammolar chiqishi mumkin, chunki {weak}."),
    "expl_ok": ("However, every friendship needs effort, so they should keep talking honestly.",
                "Biroq har bir do'stlik harakat talab qiladi, shuning uchun ular ochiq gaplashib turishi kerak."),
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
    "words": (
        "🔤 <b>Project vocabulary</b>\n\n"
        "<b>Adjectives with prefixes</b>\n"
        "un-: unfriendly, unkind, unreliable, unselfish, unhappy\n"
        "in-: impatient, insensitive, inactive, insecure\n"
        "dis-: dishonest, disorganized, disloyal, disrespectful\n\n"
        "<b>Positive adjectives</b>\n"
        "outgoing, imaginative, patient, honest, funny, kind, creative, calm, energetic, "
        "organized, loyal, curious\n\n"
        "<b>Verb + -ing</b>\n"
        "enjoy spending time · love meeting new people · avoid arguing · "
        "don't mind helping · prefer doing · can't stand waiting · hate lying\n\n"
        "<b>Example</b>\n"
        "<i>Amelia is outgoing but impatient. She enjoys meeting new people, but she can't stand waiting.</i>",
        "🔤 <b>Loyiha lug'ati</b>\n\n"
        "<b>Prefiksli sifatlar</b>\n"
        "un-: unfriendly (sovuqmuomala), unkind (mehrsiz), unreliable (ishonchsiz), "
        "unselfish (fidoyi), unhappy (baxtsiz)\n"
        "in-: impatient (sabrsiz), insensitive (his-tuyg'usiz), inactive (harakatsiz), "
        "insecure (o'ziga ishonchsiz)\n"
        "dis-: dishonest (yolg'onchi), disorganized (tartibsiz), disloyal (sadoqatsiz), "
        "disrespectful (hurmatsiz)\n\n"
        "<b>Ijobiy sifatlar</b>\n"
        "outgoing (kirishimli), imaginative (tasavvuri boy), patient (sabrli), honest (halol), "
        "funny (hazilkash), kind (mehribon), creative (ijodkor), calm (xotirjam), "
        "energetic (serharakat), organized (tartibli), loyal (sadoqatli), curious (qiziquvchan)\n\n"
        "<b>Fe'l + -ing</b>\n"
        "enjoy spending time (vaqt o'tkazishni yoqtirmoq) · love meeting new people (yangi odamlar "
        "bilan tanishishni yaxshi ko'rmoq) · avoid arguing (tortishishdan qochmoq) · "
        "don't mind helping (yordam berishga qarshi emas) · prefer doing (qilishni afzal ko'rmoq) · "
        "can't stand waiting (kutishga chidolmaslik) · hate lying (yolg'onni yomon ko'rmoq)\n\n"
        "<b>Misol</b>\n"
        "<i>Amelia is outgoing but impatient. She enjoys meeting new people, but she can't stand waiting.</i>",
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
        [b("btn_match", "menu:match"), b("btn_users", "menu:users")],
        [b("btn_project", "menu:project"), b("btn_words", "menu:words")],
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


# ══════════════════════════════════════════════════════════════════════════════
#  START / MENU / LANGUAGE / HELP / SMALL COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
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


async def words_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    await send(update, tx("words", lang), only_menu_keyboard(lang))


async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    markup = InlineKeyboardMarkup([[btn(tx("btn_another", lang), "menu:tip"),
                                    btn(tx("btn_menu", lang), "menu:main")]])
    await send(update, "💡 " + pick(random.choice(TIPS), lang), markup)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    context.user_data["state"] = None
    context.user_data.pop("draft", None)
    context.user_data.pop("test_progress", None)
    await send(update, tx("cancelled", lang), menu_keyboard(lang))


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE WIZARD
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


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"] = {}
    context.user_data["state"] = "name"
    await send(update, tx("ask_name", L(context)))


def profile_card(p, lang):
    return (
        f"👤 <b>{esc(p['name'])}</b>, {p['age']}\n\n"
        f"🧩 <b>{tx('lbl_traits', lang)}:</b> {', '.join(trait_label(k, lang) for k in p['traits'])}\n"
        f"🎯 <b>{tx('lbl_hobbies', lang)}:</b> {', '.join(hobby_label(k, lang) for k in p['hobbies'])}\n"
        f"💖 <b>{tx('lbl_wants', lang)}:</b> {', '.join(trait_label(k, lang) for k in p['wants'])}\n"
        f"🚫 <b>{tx('lbl_avoid', lang)}:</b> {', '.join(trait_label(k, lang) for k in p['avoid'])}"
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    state = context.user_data.get("state")
    draft = context.user_data.get("draft")
    text = (update.message.text or "").strip()

    if state == "name" and draft is not None:
        if not 2 <= len(text) <= 20:
            await send(update, tx("bad_name", lang))
            return
        draft["name"] = text
        context.user_data["state"] = "age"
        await send(update, tx("ask_age", lang))
    elif state == "age" and draft is not None:
        if not text.isdigit() or not 10 <= int(text) <= 25:
            await send(update, tx("bad_age", lang))
            return
        draft["age"] = int(text)
        context.user_data["state"] = None
        await send_field(update, context, "traits")
    else:
        await send(update, tx("unknown", lang), menu_keyboard(lang))


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


async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    context.user_data["test_progress"] = []
    await send(update, question_text(0, L(context)), question_keyboard(0))


# ══════════════════════════════════════════════════════════════════════════════
#  SCORING  (Personality, Common interests, Trust, Communication, Fun → /50)
# ══════════════════════════════════════════════════════════════════════════════
def compute_score(profile, answers, fake):
    wants, avoid = set(profile["wants"]), set(profile["avoid"])
    ftraits = set(fake["traits"])

    overlap = len(wants & ftraits)
    fixes = sum(1 for t in profile["traits"] if t in FIXES and FIXES[t] in ftraits)
    penalty = len(avoid & ftraits)
    personality = max(0, min(10, min(8, 2 * overlap) + min(2, fixes) - 3 * penalty))

    common = sorted(set(profile["hobbies"]) & set(fake["hobbies"]))
    interests = [2, 5, 8, 10][min(len(common), 3)]

    pts = [{0: 5, 1: 3, 2: 1}[abs(a - b)] for a, b in zip(answers, fake["answers"])]
    trust = pts[0] + pts[1]
    communication = pts[2] + pts[3]
    fun = pts[4] * 2

    total = personality + interests + trust + communication + fun
    return {
        "personality": personality, "interests": interests, "trust": trust,
        "communication": communication, "fun": fun, "total": total, "common": common,
    }


def rating(total, lang):
    for threshold, pair in RATINGS:
        if total >= threshold:
            return pick(pair, lang)
    return ""


def details_text(profile, answers, fake, lang):
    s = compute_score(profile, answers, fake)
    lines = [f"{fake['emoji']} <b>{esc(profile['name'])} ❤️ {esc(fake['name'])}</b>", ""]
    for cat in CATS:
        lines.append(f"{tx('cat_' + cat, lang)}: <b>{s[cat]}/10</b>\n<code>{bar(s[cat])}</code>")
    lines.append(f"\n<b>{tx('total', lang)}: {s['total']}/50</b> — {rating(s['total'], lang)}")
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
    lines.append(tx("expl_strong", lang, total=s["total"], strong=strong))
    if s[worst] >= 8:
        lines.append(tx("expl_ok", lang))
    else:
        lines.append(tx("expl_weak", lang, weak=pick(WEAK[worst], lang)))
    return "\n".join(lines)


def not_ready(context):
    """Return (text_key, callback, button_key) if profile / test is missing, else None."""
    ud = context.user_data
    if "profile" not in ud:
        return "need_profile", "menu:profile", "btn_make_profile"
    if "answers" not in ud:
        return "need_test", "menu:test", "btn_take_test"
    return None


def not_ready_message(context):
    lang = L(context)
    key, cb, bkey = not_ready(context)
    markup = InlineKeyboardMarkup([[btn(tx(bkey, lang), cb)], [btn(tx("btn_menu", lang), "menu:main")]])
    return tx(key, lang), markup


def match_list(context):
    """Return (text, markup) for the ranking of all fictional users."""
    lang = L(context)
    if not_ready(context):
        return not_ready_message(context)
    profile, answers = context.user_data["profile"], context.user_data["answers"]
    results = sorted(
        ((compute_score(profile, answers, f), f) for f in FAKE_USERS),
        key=lambda x: x[0]["total"], reverse=True,
    )
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 20
    lines = [tx("match_title", lang), ""]
    rows, row = [], []
    for m, (s, f) in zip(medals, results):
        lines.append(f"{m} <b>{esc(f['name'])}</b> — {s['total']}/50 · {rating(s['total'], lang)}")
        row.append(btn(f"{f['emoji']} {f['name']} ({s['total']})", f"det:{f['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn(tx("btn_menu", lang), "menu:main")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def match_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, markup = match_list(context)
    await send(update, text, markup)


# ══════════════════════════════════════════════════════════════════════════════
#  FICTIONAL USERS
# ══════════════════════════════════════════════════════════════════════════════
def fake_card(f, lang):
    return (
        f"{f['emoji']} <b>{esc(f['name'])}</b>, {f['age']}\n\n"
        f"🧩 <b>{tx('lbl_traits', lang)}:</b> {', '.join(trait_label(k, lang) for k in f['traits'])}\n"
        f"🎯 <b>{tx('lbl_hobbies', lang)}:</b> {', '.join(hobby_label(k, lang) for k in f['hobbies'])}\n"
        f"💪 <b>{tx('lbl_strength', lang)}:</b> {pick(f['strength'], lang)}\n"
        f"⚠️ <b>{tx('lbl_weakness', lang)}:</b> {pick(f['weakness'], lang)}\n"
        f"❤️ <b>{tx('lbl_likes', lang)}:</b> {esc(f['name'])} {pick(f['likes'], lang)}\n"
        f"🚫 <b>{tx('lbl_dislikes', lang)}:</b> {esc(f['name'])} {pick(f['dislikes'], lang)}"
    )


def users_markup(idx, lang):
    n = len(FAKE_USERS)
    f = FAKE_USERS[idx]
    return InlineKeyboardMarkup([
        [btn("⬅️", f"usr:{(idx - 1) % n}"), btn(f"{idx + 1}/{n}", "noop"), btn("➡️", f"usr:{(idx + 1) % n}")],
        [btn(tx("btn_score_me", lang), f"det:{f['id']}")],
        [btn(tx("btn_menu", lang), "menu:main")],
    ])


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = L(context)
    await send(update, fake_card(FAKE_USERS[0], lang), users_markup(0, lang))


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════════════════════
MENU_ACTIONS = {
    "main": menu_cmd, "profile": profile_cmd, "test": test_cmd, "match": match_cmd,
    "users": users_cmd, "project": project_cmd, "words": words_cmd, "tip": tip_cmd,
    "language": language_cmd, "help": help_cmd,
}


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    lang = L(context)
    kind, _, rest = (q.data or "").partition(":")

    # ---- language ----------------------------------------------------------
    if kind == "lang":
        new = rest if rest in ("uz", "en") else "uz"
        context.user_data["lang"] = new
        await q.answer()
        try:  # make the command panel match the chosen language for this chat
            await context.bot.set_my_commands(
                commands_for(new), scope=BotCommandScopeChat(update.effective_chat.id)
            )
        except Exception as e:  # not critical
            log.warning("set_my_commands failed: %s", e)
        await edit(update, tx("welcome", new), menu_keyboard(new))

    # ---- main menu buttons -------------------------------------------------
    elif kind == "menu":
        await q.answer()
        action = MENU_ACTIONS.get(rest)
        if action:
            await action(update, context)

    # ---- profile selections --------------------------------------------------
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
        chosen = draft.get(field, [])
        if len(chosen) < mn:
            await q.answer(tx("need_min", lang, mn=mn), show_alert=True)
            return
        await q.answer()
        idx = FIELD_ORDER.index(field)
        if idx + 1 < len(FIELD_ORDER):
            await send_field(update, context, FIELD_ORDER[idx + 1], edit_msg=True)
        else:
            profile = {
                "name": draft.get("name", "Friend"),
                "age": draft.get("age", 15),
                **{f: list(draft.get(f, [])) for f in FIELD_ORDER},
            }
            context.user_data["profile"] = profile
            context.user_data.pop("draft", None)
            markup = InlineKeyboardMarkup([
                [btn(tx("btn_take_test", lang), "menu:test")],
                [btn(tx("btn_menu", lang), "menu:main")],
            ])
            await edit(
                update,
                f"{tx('profile_saved', lang)}\n\n{profile_card(profile, lang)}\n\n{tx('next_test', lang)}",
                markup,
            )

    # ---- test answers --------------------------------------------------------
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
        else:
            context.user_data["answers"] = list(prog)
            context.user_data["test_progress"] = None
            markup = InlineKeyboardMarkup([
                [btn(tx("btn_show_match", lang), "match:list")],
                [btn(tx("btn_menu", lang), "menu:main")],
            ])
            await edit(update, tx("test_done", lang), markup)

    # ---- matches -------------------------------------------------------------
    elif kind == "match":
        await q.answer()
        text, markup = match_list(context)
        await edit(update, text, markup)

    elif kind == "det":
        await q.answer()
        fake = FAKE_BY_ID.get(rest)
        if fake is None:
            return
        if not_ready(context):
            text, markup = not_ready_message(context)
            await send(update, text, markup)
            return
        idx = FAKE_USERS.index(fake)
        markup = InlineKeyboardMarkup([
            [btn(tx("btn_card", lang), f"usr:{idx}")],
            [btn(tx("btn_back_matches", lang), "match:list")],
            [btn(tx("btn_menu", lang), "menu:main")],
        ])
        text = details_text(context.user_data["profile"], context.user_data["answers"], fake, lang)
        await edit(update, text, markup)

    # ---- fictional users pager -----------------------------------------------
    elif kind == "usr":
        await q.answer()
        try:
            idx = int(rest) % len(FAKE_USERS)
        except ValueError:
            return
        await edit(update, fake_card(FAKE_USERS[idx], lang), users_markup(idx, lang))

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
    if TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise SystemExit("❌ Set your bot token: BOT_TOKEN=... python friend_match_bot.py "
                         "(get it from @BotFather)")

    persistence = PicklePersistence(filepath="friend_match_data.pkl")  # remembers language & profiles
    app = Application.builder().token(TOKEN).persistence(persistence).post_init(post_init).build()

    for name, handler in [
        ("start", start), ("menu", menu_cmd), ("profile", profile_cmd), ("test", test_cmd),
        ("match", match_cmd), ("users", users_cmd), ("project", project_cmd),
        ("words", words_cmd), ("tip", tip_cmd), ("language", language_cmd),
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
