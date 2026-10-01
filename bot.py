import asyncio
import random
import os
import tempfile
import hashlib
import threading
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, CallbackQuery
)
from aiogram.client.default import DefaultBotProperties
from flask import Flask
import edge_tts


BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SITE_URL = "https://smartenglishhub.netlify.app"
SITE_QR = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={SITE_URL}"

VOICE_KK = "kk-KZ-AigulNeural"
VOICE_EN = "en-US-AriaNeural"

CACHE_DIR = os.path.join(tempfile.gettempdir(), "buddy_voice_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

app = Flask(__name__)


USERS = {}
LEARNED = {}


def new_user(first_name, username=""):
    return {
        "first_name": first_name, "username": username,
        "xp": 0, "streak": 1, "last_seen": date.today().isoformat(),
        "learned": 0, "correct_answers": 0, "total_answers": 0,
    }


def ensure_user(user):
    uid = user.id
    today = date.today().isoformat()
    if uid not in USERS:
        USERS[uid] = new_user(user.first_name, user.username or "")
        LEARNED[uid] = set()
        return
    u = USERS[uid]
    if u["last_seen"] != today:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        u["streak"] = u["streak"] + 1 if u["last_seen"] == yesterday else 1
        u["last_seen"] = today
    u["first_name"] = user.first_name
    u["username"] = user.username or ""


def add_xp(uid, amount):
    if uid in USERS:
        USERS[uid]["xp"] += amount


def mark_learned(uid, kz):
    if uid not in USERS:
        return
    if uid not in LEARNED:
        LEARNED[uid] = set()
    if kz not in LEARNED[uid]:
        LEARNED[uid].add(kz)
        USERS[uid]["learned"] = len(LEARNED[uid])


def update_stats(uid, correct):
    if uid in USERS:
        USERS[uid]["total_answers"] += 1
        if correct:
            USERS[uid]["correct_answers"] += 1


DICT = {
    "кітап": ("book", "🏫 Мектеп"), "мұғалім": ("teacher", "🏫 Мектеп"),
    "оқушы": ("student", "🏫 Мектеп"), "сынып": ("classroom", "🏫 Мектеп"),
    "сабақ": ("lesson", "🏫 Мектеп"), "тақта": ("blackboard", "🏫 Мектеп"),
    "кітапхана": ("library", "🏫 Мектеп"), "үй жұмысы": ("homework", "🏫 Мектеп"),
    "үзіліс": ("break", "🏫 Мектеп"), "қарындаш": ("pencil", "🏫 Мектеп"),
    "мектеп": ("school", "🏫 Мектеп"), "қалам": ("pen", "🏫 Мектеп"),
    "дәптер": ("notebook", "🏫 Мектеп"), "қоңырау": ("bell", "🏫 Мектеп"),
    "емтихан": ("exam", "🏫 Мектеп"), "баға": ("grade", "🏫 Мектеп"),
    "сұрақ": ("question", "🏫 Мектеп"), "жауап": ("answer", "🏫 Мектеп"),
    "тапсырма": ("task", "🏫 Мектеп"), "сыныптас": ("classmate", "🏫 Мектеп"),
    "оқулық": ("textbook", "🏫 Мектеп"), "күнделік": ("diary", "🏫 Мектеп"),
    "өшіргіш": ("eraser", "🏫 Мектеп"), "сызғыш": ("ruler", "🏫 Мектеп"),
    "карта": ("map", "🏫 Мектеп"), "тарих": ("history", "🏫 Мектеп"),
    "математика": ("math", "🏫 Мектеп"), "физика": ("physics", "🏫 Мектеп"),
    "химия": ("chemistry", "🏫 Мектеп"), "биология": ("biology", "🏫 Мектеп"),

    "алма": ("apple", "🍎 Тағам"), "нан": ("bread", "🍎 Тағам"),
    "сүт": ("milk", "🍎 Тағам"), "су": ("water", "🍎 Тағам"),
    "ет": ("meat", "🍎 Тағам"), "ірімшік": ("cheese", "🍎 Тағам"),
    "көкөніс": ("vegetable", "🍎 Тағам"), "жеміс": ("fruit", "🍎 Тағам"),
    "шай": ("tea", "🍎 Тағам"), "сорпа": ("soup", "🍎 Тағам"),
    "банан": ("banana", "🍎 Тағам"), "жұмыртқа": ("egg", "🍎 Тағам"),
    "балық": ("fish", "🍎 Тағам"), "күріш": ("rice", "🍎 Тағам"),
    "тұз": ("salt", "🍎 Тағам"), "қант": ("sugar", "🍎 Тағам"),
    "пияз": ("onion", "🍎 Тағам"), "картоп": ("potato", "🍎 Тағам"),
    "қызанақ": ("tomato", "🍎 Тағам"), "қияр": ("cucumber", "🍎 Тағам"),
    "кофе": ("coffee", "🍎 Тағам"), "торт": ("cake", "🍎 Тағам"),
    "балмұздақ": ("ice cream", "🍎 Тағам"), "шоколад": ("chocolate", "🍎 Тағам"),
    "бал": ("honey", "🍎 Тағам"), "шайнек": ("teapot", "🍎 Тағам"),

    "ас үй": ("kitchen", "🏠 Үй"), "жатын бөлме": ("bedroom", "🏠 Үй"),
    "отбасы": ("family", "🏠 Үй"), "қонақ бөлме": ("living room", "🏠 Үй"),
    "бақ": ("garden", "🏠 Үй"), "терезе": ("window", "🏠 Үй"),
    "есік": ("door", "🏠 Үй"), "үстел": ("table", "🏠 Үй"),
    "орындық": ("chair", "🏠 Үй"), "төсек": ("bed", "🏠 Үй"),
    "үй": ("house", "🏠 Үй"), "шам": ("lamp", "🏠 Үй"),
    "айна": ("mirror", "🏠 Үй"), "кілт": ("key", "🏠 Үй"),
    "ванна": ("bathroom", "🏠 Үй"), "қабырға": ("wall", "🏠 Үй"),
    "еден": ("floor", "🏠 Үй"), "төбе": ("ceiling", "🏠 Үй"),
    "баспалдақ": ("stairs", "🏠 Үй"), "диван": ("sofa", "🏠 Үй"),
    "кілем": ("carpet", "🏠 Үй"), "теледидар": ("TV", "🏠 Үй"),
    "тоңазытқыш": ("fridge", "🏠 Үй"), "шаңсорғыш": ("vacuum cleaner", "🏠 Үй"),

    "дәрігер": ("doctor", "🏥 Денсаулық"), "бас ауруы": ("headache", "🏥 Денсаулық"),
    "сау": ("healthy", "🏥 Денсаулық"), "дәрі": ("medicine", "🏥 Денсаулық"),
    "спорт": ("sport", "🏥 Денсаулық"), "аурухана": ("hospital", "🏥 Денсаулық"),
    "медбике": ("nurse", "🏥 Денсаулық"), "ұйқы": ("sleep", "🏥 Денсаулық"),
    "витамин": ("vitamin", "🏥 Денсаулық"), "ауру": ("illness", "🏥 Денсаулық"),
    "ем": ("treatment", "🏥 Денсаулық"), "жүгіру": ("running", "🏥 Денсаулық"),
    "жүзу": ("swimming", "🏥 Денсаулық"), "денсаулық": ("health", "🏥 Денсаулық"),
    "тәбет": ("appetite", "🏥 Денсаулық"), "тісті дәрігер": ("dentist", "🏥 Денсаулық"),

    "домбыра": ("dombra", "🇰🇿 Қазақстан"), "киіз үй": ("yurt", "🇰🇿 Қазақстан"),
    "ту": ("flag", "🇰🇿 Қазақстан"), "дала": ("steppe", "🇰🇿 Қазақстан"),
    "байқоңыр": ("Baikonur", "🇰🇿 Қазақстан"), "астана": ("Astana", "🇰🇿 Қазақстан"),
    "алматы": ("Almaty", "🇰🇿 Қазақстан"), "бүркіт": ("eagle", "🇰🇿 Қазақстан"),
    "наурыз": ("Nauryz", "🇰🇿 Қазақстан"), "қымыз": ("kumys", "🇰🇿 Қазақстан"),
    "павлодар": ("Pavlodar", "🇰🇿 Қазақстан"), "отан": ("motherland", "🇰🇿 Қазақстан"),
    "халық": ("people", "🇰🇿 Қазақстан"), "тіл": ("language", "🇰🇿 Қазақстан"),
    "әнұран": ("anthem", "🇰🇿 Қазақстан"), "шаңырақ": ("shanyrak", "🇰🇿 Қазақстан"),

    "сәлем": ("hello", "👋 Сәлемдесу"), "рахмет": ("thank you", "👋 Сәлемдесу"),
    "қош бол": ("goodbye", "👋 Сәлемдесу"), "иә": ("yes", "👋 Сәлемдесу"),
    "жоқ": ("no", "👋 Сәлемдесу"), "кешіріңіз": ("sorry", "👋 Сәлемдесу"),
    "қалайсың": ("how are you", "👋 Сәлемдесу"), "жақсы": ("good", "👋 Сәлемдесу"),
    "қайырлы таң": ("good morning", "👋 Сәлемдесу"),
    "қайырлы түн": ("good night", "👋 Сәлемдесу"),
    "қош келдіңіз": ("welcome", "👋 Сәлемдесу"),
    "өтінемін": ("please", "👋 Сәлемдесу"),
    "қайырлы күн": ("good afternoon", "👋 Сәлемдесу"),

    "мен": ("I", "👨‍👩‍👧 Адамдар"), "сен": ("you", "👨‍👩‍👧 Адамдар"),
    "ол": ("he/she", "👨‍👩‍👧 Адамдар"), "біз": ("we", "👨‍👩‍👧 Адамдар"),
    "олар": ("they", "👨‍👩‍👧 Адамдар"), "ана": ("mother", "👨‍👩‍👧 Адамдар"),
    "әке": ("father", "👨‍👩‍👧 Адамдар"), "аға": ("brother", "👨‍👩‍👧 Адамдар"),
    "апа": ("sister", "👨‍👩‍👧 Адамдар"), "бала": ("child", "👨‍👩‍👧 Адамдар"),
    "дос": ("friend", "👨‍👩‍👧 Адамдар"), "әже": ("grandmother", "👨‍👩‍👧 Адамдар"),
    "ата": ("grandfather", "👨‍👩‍👧 Адамдар"), "немере": ("grandchild", "👨‍👩‍👧 Адамдар"),
    "ұл": ("son", "👨‍👩‍👧 Адамдар"), "қыз": ("daughter", "👨‍👩‍👧 Адамдар"),

    "қала": ("city", "🏙 Қала"), "ауыл": ("village", "🏙 Қала"),
    "жол": ("road", "🏙 Қала"), "көше": ("street", "🏙 Қала"),
    "машина": ("car", "🏙 Қала"), "пойыз": ("train", "🏙 Қала"),
    "ұшақ": ("plane", "🏙 Қала"), "дүкен": ("shop", "🏙 Қала"),
    "банк": ("bank", "🏙 Қала"), "саябақ": ("park", "🏙 Қала"),
    "мұражай": ("museum", "🏙 Қала"), "театр": ("theater", "🏙 Қала"),
    "аялдама": ("bus stop", "🏙 Қала"), "көпір": ("bridge", "🏙 Қала"),
    "бағдаршам": ("traffic lights", "🏙 Қала"),

    "күн": ("sun", "🌍 Табиғат"), "ай": ("moon", "🌍 Табиғат"),
    "жұлдыз": ("star", "🌍 Табиғат"), "аспан": ("sky", "🌍 Табиғат"),
    "теңіз": ("sea", "🌍 Табиғат"), "тау": ("mountain", "🌍 Табиғат"),
    "өзен": ("river", "🌍 Табиғат"), "орман": ("forest", "🌍 Табиғат"),
    "гүл": ("flower", "🌍 Табиғат"), "ағаш": ("tree", "🌍 Табиғат"),
    "жаңбыр": ("rain", "🌍 Табиғат"), "қар": ("snow", "🌍 Табиғат"),
    "жел": ("wind", "🌍 Табиғат"), "бұлт": ("cloud", "🌍 Табиғат"),
    "кемпірқосақ": ("rainbow", "🌍 Табиғат"), "от": ("fire", "🌍 Табиғат"),

    "ит": ("dog", "🐾 Жануарлар"), "мысық": ("cat", "🐾 Жануарлар"),
    "құс": ("bird", "🐾 Жануарлар"), "балық": ("fish", "🐾 Жануарлар"),
    "жылқы": ("horse", "🐾 Жануарлар"), "сиыр": ("cow", "🐾 Жануарлар"),
    "қой": ("sheep", "🐾 Жануарлар"), "түйе": ("camel", "🐾 Жануарлар"),
    "арыстан": ("lion", "🐾 Жануарлар"), "жолбарыс": ("tiger", "🐾 Жануарлар"),
    "піл": ("elephant", "🐾 Жануарлар"), "қоян": ("rabbit", "🐾 Жануарлар"),
    "түлкі": ("fox", "🐾 Жануарлар"), "қасқыр": ("wolf", "🐾 Жануарлар"),
    "мысықбала": ("kitten", "🐾 Жануарлар"), "күшік": ("puppy", "🐾 Жануарлар"),

    "қызыл": ("red", "🎨 Түстер"), "көк": ("blue", "🎨 Түстер"),
    "жасыл": ("green", "🎨 Түстер"), "сары": ("yellow", "🎨 Түстер"),
    "қара": ("black", "🎨 Түстер"), "ақ": ("white", "🎨 Түстер"),
    "қоңыр": ("brown", "🎨 Түстер"), "қызғылт": ("pink", "🎨 Түстер"),
    "күлгін": ("purple", "🎨 Түстер"), "сұр": ("gray", "🎨 Түстер"),

    "бір": ("one", "🔢 Сандар"), "екі": ("two", "🔢 Сандар"),
    "үш": ("three", "🔢 Сандар"), "төрт": ("four", "🔢 Сандар"),
    "бес": ("five", "🔢 Сандар"), "алты": ("six", "🔢 Сандар"),
    "жеті": ("seven", "🔢 Сандар"), "сегіз": ("eight", "🔢 Сандар"),
    "тоғыз": ("nine", "🔢 Сандар"), "он": ("ten", "🔢 Сандар"),
    "жиырма": ("twenty", "🔢 Сандар"), "жүз": ("hundred", "🔢 Сандар"),
    "мың": ("thousand", "🔢 Сандар"),

    "уақыт": ("time", "⏰ Уақыт"), "сағат": ("hour", "⏰ Уақыт"),
    "минут": ("minute", "⏰ Уақыт"), "апта": ("week", "⏰ Уақыт"),
    "жыл": ("year", "⏰ Уақыт"), "бүгін": ("today", "⏰ Уақыт"),
    "ертең": ("tomorrow", "⏰ Уақыт"), "кеше": ("yesterday", "⏰ Уақыт"),
    "дүйсенбі": ("Monday", "⏰ Уақыт"), "сейсенбі": ("Tuesday", "⏰ Уақыт"),
    "сәрсенбі": ("Wednesday", "⏰ Уақыт"), "бейсенбі": ("Thursday", "⏰ Уақыт"),
    "жұма": ("Friday", "⏰ Уақыт"), "сенбі": ("Saturday", "⏰ Уақыт"),
    "жексенбі": ("Sunday", "⏰ Уақыт"),
}

DICT_EN = {}
for kz, (en, cat) in DICT.items():
    ek = en.lower()
    if ek not in DICT_EN:
        DICT_EN[ek] = (kz, cat)

CATEGORIES = {}
for kz, (en, cat) in DICT.items():
    CATEGORIES.setdefault(cat, []).append(kz)


GRAMMAR = {
    "present_simple": {
        "title": "Present Simple",
        "rule": "Қазіргі уақытта жиі болып тұратын іс-әрекеттер. I/you/we/they → V1. He/she/it → V1+s.",
        "examples": [
            "I play football every day. — Мен күнде футбол ойнаймын.",
            "She goes to school. — Ол мектепке барады.",
            "They study English. — Олар ағылшын тілін оқиды."
        ]
    },
    "past_simple": {
        "title": "Past Simple",
        "rule": "Өткен уақытта болған іс-әрекет. Тұрақты етістікке -ed қосылады.",
        "examples": [
            "I played football yesterday. — Мен кеше футбол ойнадым.",
            "He went to school. — Ол мектепке барды.",
            "We visited Pavlodar. — Біз Павлодарға бардық."
        ]
    },
    "there_is_are": {
        "title": "There is / There are",
        "rule": "There is — жекеше зат үшін. There are — көпше зат үшін.",
        "examples": [
            "There is a book on the table. — Үстелде кітап бар.",
            "There are books on the shelf. — Сөреде кітаптар бар."
        ]
    },
    "present_continuous": {
        "title": "Present Continuous",
        "rule": "Қазір болып жатқан іс-әрекет. am/is/are + V-ing.",
        "examples": [
            "I am reading now. — Мен қазір оқып отырмын.",
            "She is writing a letter. — Ол хат жазып отыр."
        ]
    },
    "articles": {
        "title": "Articles a / an / the",
        "rule": "Дауысты дыбыстан басталса — an. Дауыссыздан — a. Белгілі затқа — the.",
        "examples": ["a book — кітап", "an apple — алма", "the school — сол мектеп"]
    },
    "plural": {
        "title": "Plural nouns",
        "rule": "Көптік жалғау: -s немесе -es. Ерекше: child → children, man → men.",
        "examples": ["book → books", "box → boxes", "child → children"]
    },
    "possessive": {
        "title": "Possessive 's",
        "rule": "Затқа -'s қосылады.",
        "examples": [
            "This is Ayan's book. — Бұл Аянның кітабы.",
            "My mother's car. — Менің анамның көлігі."
        ]
    },
    "modal": {
        "title": "Modal verbs can / must",
        "rule": "Can — мүмкіндік. Must — міндеттілік.",
        "examples": [
            "I can swim. — Мен жүзе аламын.",
            "You must do your homework. — Сен үй жұмысын орындауың керек."
        ]
    }
}


PROMPTS = [
    ("📝 Грамматика тексеру",
     "I am a 6th-grade student from Kazakhstan. Check my text for grammar mistakes, fix them, and explain the rules simply in Kazakh."),
    ("📖 Сөздікпен оқу",
     "Write a 5-sentence funny story using these words: subject, timetable, library, homework. Give Kazakh translation for each sentence."),
    ("💬 Диалог жаттығуы",
     "Let's have a friendly English dialogue about 'My School'. Ask me 5 questions and correct my mistakes."),
    ("🔤 Тест жасау",
     "Create a multiple-choice quiz for 6th grade on topic 'My School'. Give 5 questions with answers."),
    ("🎤 Айтылым жаттығуы",
     "Give me 5 English tongue-twisters for 6th grade with Kazakh translation and pronunciation tips."),
    ("✍️ Эссе көмегі",
     "Help me write a short essay (100 words) in English about 'My Favourite Subject'. Use simple words for 6th grade."),
]


def get_level(xp):
    if xp < 100: return "🥉 A1 Beginner", 0, 100
    if xp < 300: return "🥈 A2 Elementary", 100, 300
    if xp < 600: return "🥇 B1 Intermediate", 300, 600
    if xp < 1000: return "💎 B2 Upper-Int", 600, 1000
    return "👑 C1 Advanced", 1000, 2000


def progress_bar(current, total, size=10):
    filled = int(size * current / total) if total else 0
    return "🟢" * filled + "⚪" * (size - filled)


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 Аудару"), KeyboardButton(text="📚 Грамматика")],
            [KeyboardButton(text="🎮 Викторина"), KeyboardButton(text="🎲 Кездейсоқ сөз")],
            [KeyboardButton(text="📖 Сөздік"), KeyboardButton(text="📅 Слово дня")],
            [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="💡 Промпттар")],
            [KeyboardButton(text="🔗 Сайт + QR"), KeyboardButton(text="ℹ️ Көмек")],
        ],
        resize_keyboard=True
    )


def site_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Сайтты ашу", url=SITE_URL)],
        [InlineKeyboardButton(text="📱 QR-код алу", callback_data="qr")]
    ])


async def make_voice(text: str, lang: str) -> str:
    voice = VOICE_KK if lang == "kk" else VOICE_EN
    key = hashlib.md5(f"{lang}_{text}".encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{key}.mp3")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(cache_path)
    return cache_path


WORDS_PER_PAGE = 6


def build_words_page(cat: str, page: int):
    words = CATEGORIES.get(cat, [])
    total_pages = (len(words) + WORDS_PER_PAGE - 1) // WORDS_PER_PAGE
    page = max(0, min(page, total_pages - 1))

    start = page * WORDS_PER_PAGE
    end = start + WORDS_PER_PAGE
    page_words = words[start:end]

    text = (
        f"<b>{cat}</b>\n"
        f"Бет {page + 1}/{total_pages}\n\n"
        f"👇 <b>Сөзге басыңыз</b> — қазақша, содан кейін ағылшынша естисіз\n"
    )

    kb_rows = []
    for kz in page_words:
        en, _ = DICT[kz]
        kb_rows.append([
            InlineKeyboardButton(
                text=f"🇰🇿 {kz}  ·  🇬🇧 {en}",
                callback_data=f"w_pair_{kz}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Артқа", callback_data=f"pg_{cat}_{page - 1}"
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}", callback_data="noop"
    ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="Алға ▶️", callback_data=f"pg_{cat}_{page + 1}"
        ))
    kb_rows.append(nav_row)

    kb_rows.append([InlineKeyboardButton(
        text="📂 Категориялар", callback_data="back_to_cats"
    )])

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@dp.message(CommandStart())
async def start(msg: Message):
    ensure_user(msg.from_user)
    uid = msg.from_user.id
    u = USERS[uid]
    lvl, _, _ = get_level(u["xp"])

    await msg.answer(
        f"🎉 <b>Сәлем, {msg.from_user.first_name}!</b>\n\n"
        f"🤖 Мен — <b>AI English Buddy</b>\n"
        f"Ағылшын тілін үйренуге арналған көмекшімің!\n\n"
        f"📊 <b>Сенің деңгейің:</b> {lvl}\n"
        f"⭐ XP: <b>{u['xp']}</b>  |  🔥 Streak: <b>{u['streak']}</b> күн\n\n"
        f"✨ <b>Мүмкіндіктер:</b>\n"
        f"🔊 Екі тілде озвучка\n"
        f"🎮 Викторина ойыны\n"
        f"📖 {len(DICT)} сөз сөздігі\n"
        f"📅 Күн сайын жаңа сөз\n\n"
        f"Төмендегі мәзірден таңдаңыз 👇",
        reply_markup=main_menu()
    )


@dp.message(F.text == "🌐 Аудару")
async def translate_help(msg: Message):
    await msg.answer(
        "🌐 <b>Аудару</b>\n\n"
        "Қазақша <b>немесе</b> ағылшынша сөз жазыңыз — мен аударып, "
        "екі тілде дыбыстаймын! 🔊\n\n"
        "💡 <b>Мысалдар:</b>\n"
        "🇰🇿 <code>кітап</code> → 🇬🇧 <b>book</b>\n"
        "🇬🇧 <code>teacher</code> → 🇰🇿 <b>мұғалім</b>\n"
        "🇰🇿 <code>дәрігер</code> → 🇬🇧 <b>doctor</b>"
    )


@dp.message(F.text == "📚 Грамматика")
async def grammar_menu(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📘 {g['title']}", callback_data=f"g_{k}")]
        for k, g in GRAMMAR.items()
    ])
    await msg.answer(
        "📚 <b>Грамматика</b>\n\n"
        "6-сыныпқа арналған 8 ереже.\n\n"
        "Керек ережені таңдаңыз 👇",
        reply_markup=kb
    )


@dp.callback_query(F.data.startswith("g_"))
async def show_grammar(call: CallbackQuery):
    key = call.data[2:]
    g = GRAMMAR.get(key)
    if not g:
        return await call.answer("Табылмады", show_alert=True)
    text = f"📚 <b>{g['title']}</b>\n\n"
    text += f"📌 <b>Ереже:</b>\n{g['rule']}\n\n"
    text += "✨ <b>Мысалдар:</b>\n"
    for ex in g["examples"]:
        text += f"  ▸ <i>{ex}</i>\n"
    await call.message.answer(text)
    await call.answer()


@dp.message(F.text == "🎮 Викторина")
async def quiz_start_msg(msg: Message):
    ensure_user(msg.from_user)
    await start_quiz(msg)


async def start_quiz(msg, edit=False):
    kz = random.choice(list(DICT.keys()))
    en, _ = DICT[kz]
    options = [en]
    while len(options) < 4:
        r = random.choice(list(DICT.values()))[0]
        if r not in options:
            options.append(r)
    random.shuffle(options)

    letters = ["🅰️", "🅱️", "©️", "🆔"]
    text = (
        f"🎮 <b>Викторина</b>\n\n"
        f"❓ «<b>{kz}</b>» сөзінің ағылшынша аудармасы?\n\n"
    )
    kb_rows = []
    for i, opt in enumerate(options):
        text += f"{letters[i]} {opt}\n"
        kb_rows.append([InlineKeyboardButton(
            text=f"{letters[i]} {opt}",
            callback_data=f"qa_{kz}_{opt}"
        )])
    kb_rows.append([InlineKeyboardButton(text="🚫 Тоқтату", callback_data="quiz_stop")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    if edit:
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.answer(text, reply_markup=markup)


@dp.callback_query(F.data.startswith("qa_"))
async def quiz_answer(call: CallbackQuery):
    parts = call.data.split("_", 2)
    kz = parts[1]
    chosen = parts[2]
    correct_en, _ = DICT[kz]
    uid = call.from_user.id
    ensure_user(call.from_user)

    if chosen == correct_en:
        add_xp(uid, 10)
        update_stats(uid, True)
        text = f"✅ <b>ДҰРЫС!</b> 🎉\n\n🇰🇿 {kz} = 🇬🇧 <b>{correct_en}</b>\n\n+10 XP ⭐"
    else:
        update_stats(uid, False)
        text = f"❌ <b>ҚАТЕ</b>\n\n🇰🇿 {kz} = 🇬🇧 <b>{correct_en}</b>\n\nСен таңдадың: {chosen}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Келесі сұрақ", callback_data="quiz_next")],
        [InlineKeyboardButton(text="🚫 Тоқтату", callback_data="quiz_stop")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data == "quiz_next")
async def quiz_next(call: CallbackQuery):
    await start_quiz(call.message, edit=True)
    await call.answer()


@dp.callback_query(F.data == "quiz_stop")
async def quiz_stop(call: CallbackQuery):
    await call.message.edit_text("🎮 Викторина аяқталды! Қайта ойнау үшін мәзірден «🎮 Викторина» басыңыз.")
    await call.answer("Тоқтатылды")


@dp.message(F.text == "🎲 Кездейсоқ сөз")
async def random_word_msg(msg: Message):
    ensure_user(msg.from_user)
    kz = random.choice(list(DICT.keys()))
    en, cat = DICT[kz]
    await msg.answer("🎲 <b>Кездейсоқ сөз:</b>")
    await msg.answer(
        f"{cat}\n\n🇰🇿 <b>{kz}</b>\n🇬🇧 <b>{en}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔊 Тыңдау: {kz} · {en}",
                callback_data=f"w_pair_{kz}"
            )],
            [InlineKeyboardButton(text="🎲 Тағы бір сөз", callback_data="random_word")],
        ])
    )
    mark_learned(msg.from_user.id, kz)
    add_xp(msg.from_user.id, 5)


@dp.callback_query(F.data == "random_word")
async def random_word_cb(call: CallbackQuery):
    ensure_user(call.from_user)
    kz = random.choice(list(DICT.keys()))
    en, cat = DICT[kz]
    await call.message.answer(
        f"🎲 {cat}\n\n🇰🇿 <b>{kz}</b>\n🇬🇧 <b>{en}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔊 Тыңдау: {kz} · {en}",
                callback_data=f"w_pair_{kz}"
            )],
            [InlineKeyboardButton(text="🎲 Тағы бір сөз", callback_data="random_word")],
        ])
    )
    mark_learned(call.from_user.id, kz)
    add_xp(call.from_user.id, 5)
    await call.answer("🎲")


@dp.message(F.text == "📅 Слово дня")
async def daily_word(msg: Message):
    ensure_user(msg.from_user)
    today = date.today().toordinal()
    words = list(DICT.keys())
    kz = words[today % len(words)]
    en, cat = DICT[kz]
    await msg.answer(f"📅 <b>Күннің сөзі</b> — {date.today().strftime('%d.%m.%Y')}")
    await msg.answer(
        f"{cat}\n\n🇰🇿 <b>{kz}</b>\n🇬🇧 <b>{en}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔊 Тыңдау: {kz} · {en}",
                callback_data=f"w_pair_{kz}"
            )],
        ])
    )
    mark_learned(msg.from_user.id, kz)
    add_xp(msg.from_user.id, 5)


@dp.message(F.text == "📖 Сөздік")
async def vocab_menu(msg: Message):
    kb_rows = []
    cats = sorted(CATEGORIES.keys())
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(text=cats[i], callback_data=f"cat_{cats[i]}_0")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(
                text=cats[i + 1], callback_data=f"cat_{cats[i + 1]}_0"
            ))
        kb_rows.append(row)

    await msg.answer(
        f"📖 <b>Интерактивті сөздік</b>\n\n"
        f"Барлығы: <b>{len(DICT)}</b> сөз\n"
        f"Категориялар: <b>{len(CATEGORIES)}</b>\n\n"
        f"👇 Категорияны таңдаңыз, сосын <b>сөзге басыңыз</b> — "
        f"қазақша, содан кейін ағылшынша естисіз! 🔊",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )


@dp.callback_query(F.data.startswith("cat_"))
async def show_category(call: CallbackQuery):
    payload = call.data[4:]
    *cat_parts, page_str = payload.rsplit("_", 1)
    cat = "_".join(cat_parts)
    try:
        page = int(page_str)
    except ValueError:
        page = 0

    words = CATEGORIES.get(cat)
    if not words:
        return await call.answer("Категория табылмады", show_alert=True)

    text, kb = build_words_page(cat, page)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("pg_"))
async def pagination(call: CallbackQuery):
    payload = call.data[3:]
    *cat_parts, page_str = payload.rsplit("_", 1)
    cat = "_".join(cat_parts)
    try:
        page = int(page_str)
    except ValueError:
        page = 0

    text, kb = build_words_page(cat, page)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(call: CallbackQuery):
    kb_rows = []
    cats = sorted(CATEGORIES.keys())
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(text=cats[i], callback_data=f"cat_{cats[i]}_0")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(
                text=cats[i + 1], callback_data=f"cat_{cats[i + 1]}_0"
            ))
        kb_rows.append(row)

    try:
        await call.message.edit_text(
            f"📖 <b>Интерактивті сөздік</b>\n\n"
            f"Категорияны таңдаңыз 👇",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
        )
    except Exception:
        await call.message.answer(
            "📖 Категорияны таңдаңыз 👇",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
        )
    await call.answer()


@dp.callback_query(F.data.startswith("w_pair_"))
async def word_pair(call: CallbackQuery):
    kz = call.data[7:]
    en, _ = DICT.get(kz, (kz, ""))
    ensure_user(call.from_user)

    await call.answer("🔊 2 аудио жіберіліп жатыр...")

    try:
        path_kk = await make_voice(kz, "kk")
        await call.message.answer_voice(
            FSInputFile(path_kk),
            caption=f"🇰🇿 <b>{kz}</b>"
        )

        path_en = await make_voice(en, "en")
        await call.message.answer_voice(
            FSInputFile(path_en),
            caption=f"🇬🇧 <b>{en}</b>"
        )

        mark_learned(call.from_user.id, kz)
        add_xp(call.from_user.id, 2)
    except Exception as e:
        await call.message.answer(f"❌ Қате: {e}")


@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


@dp.message(F.text == "📊 Профиль")
async def profile(msg: Message):
    ensure_user(msg.from_user)
    uid = msg.from_user.id
    u = USERS[uid]
    xp = u["xp"]
    correct = u["correct_answers"]
    total = u["total_answers"]
    lvl, cur, need = get_level(xp)
    accuracy = int(100 * correct / total) if total else 0
    prog = progress_bar(xp - cur, need - cur)

    await msg.answer(
        f"📊 <b>Профиль</b>\n\n"
        f"👤 <b>{msg.from_user.first_name}</b>\n"
        f"🎯 Деңгей: <b>{lvl}</b>\n"
        f"{prog}  {xp}/{need} XP\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"  ⭐ XP: <b>{xp}</b>\n"
        f"  🔥 Streak: <b>{u['streak']}</b> күн\n"
        f"  📖 Оқылған сөздер: <b>{u['learned']}</b>\n"
        f"  🎮 Викторина: <b>{correct}/{total}</b> ({accuracy}%)\n\n"
        f"💪 Жалғастыр — C1 деңгейіне жету үшін тағы XP жина!"
    )


@dp.message(F.text == "💡 Промпттар")
async def prompts_menu(msg: Message):
    kb_buttons = []
    for i, (name, _) in enumerate(PROMPTS):
        kb_buttons.append([InlineKeyboardButton(text=name, callback_data=f"p_{i}")])
    await msg.answer(
        "💡 <b>Промпттар</b>\n\n"
        "ChatGPT / DeepSeek үшін дайын сұраныстар.\n\n"
        "Керек промптты таңдаңыз 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    )


@dp.callback_query(F.data.startswith("p_"))
async def show_prompt(call: CallbackQuery):
    idx = int(call.data[2:])
    name, text = PROMPTS[idx]
    await call.message.answer(
        f"{name}\n\n<b>Промпт:</b>\n<code>{text}</code>\n\n"
        f"👆 Көшіріп, ChatGPT/DeepSeek-ке жіберіңіз!"
    )
    await call.answer("✅ Дайын!")


@dp.message(F.text == "🔗 Сайт + QR")
async def site_qr(msg: Message):
    await msg.answer_photo(
        photo=SITE_QR,
        caption=(
            "🌐 <b>Smart English Hub</b>\n\n"
            f"🔗 {SITE_URL}\n\n"
            "📱 QR-кодты сканерлеп, телефонда ашыңыз!\n\n"
            "Сайтта:\n"
            "• 🎯 8 үздік қосымша\n"
            "• 💡 12 авторлық промпт\n"
            "• 📖 50 сөз сөздігі\n"
            "• 📚 8 грамматика ережесі\n"
            "• 📝 15 сұрақтық тест"
        ),
        reply_markup=site_kb()
    )


@dp.callback_query(F.data == "qr")
async def qr_cb(call: CallbackQuery):
    await call.message.answer_photo(
        photo=SITE_QR,
        caption=f"📱 QR-код:\n{SITE_URL}\n\nСканерлеп, сайтты ашыңыз!"
    )
    await call.answer()


@dp.message(F.text == "ℹ️ Көмек")
async def help_msg(msg: Message):
    await msg.answer(
        "ℹ️ <b>Көмек — AI Buddy</b>\n\n"
        "📌 <b>Мүмкіндіктер:</b>\n\n"
        "🌐 <b>Аудару</b> — KK ⇄ EN аударма + озвучка\n"
        "📚 <b>Грамматика</b> — 8 ереже мысалдарымен\n"
        "🎮 <b>Викторина</b> — ойын + XP\n"
        "🎲 <b>Кездейсоқ сөз</b> — кездейсоқ сөз\n"
        f"📖 <b>Сөздік</b> — {len(DICT)} сөз, {len(CATEGORIES)} категория\n"
        "   <i>Сөзге бассаң — 2 аудио естисің (KK + EN) 🔊</i>\n"
        "📊 <b>Профиль</b> — XP, деңгей, статистика\n"
        "📅 <b>Слово дня</b> — күннің сөзі\n"
        "💡 <b>Промпттар</b> — ChatGPT сұраныстары\n"
        "🔗 <b>Сайт + QR</b> — Smart English Hub\n\n"
        "💡 <b>Кеңес:</b> Қазақша немесе ағылшынша сөз жазыңыз — "
        "мен аударып, дыбыстаймын! 🔊\n\n"
        f"🌐 {SITE_URL}"
    )


@dp.message(F.text)
async def handle_text(msg: Message):
    ensure_user(msg.from_user)
    raw = msg.text.strip()
    text = raw.lower()
    for ch in ".,!?;:—–-":
        text = text.replace(ch, "")
    text = text.strip()

    if text in DICT:
        en, cat = DICT[text]
        await msg.answer(
            f"{cat}\n\n🇰🇿 <b>{raw}</b>\n🇬🇧 <b>{en}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"🔊 Тыңдау: {raw} · {en}",
                    callback_data=f"w_pair_{raw}"
                )],
                [InlineKeyboardButton(text="🎲 Тағы бір сөз", callback_data="random_word")],
            ])
        )
        mark_learned(msg.from_user.id, raw)
        add_xp(msg.from_user.id, 5)
        return

    if text in DICT_EN:
        kz, cat = DICT_EN[text]
        await msg.answer(
            f"{cat}\n\n🇰🇿 <b>{kz}</b>\n🇬🇧 <b>{raw}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"🔊 Тыңдау: {kz} · {raw}",
                    callback_data=f"w_pair_{kz}"
                )],
                [InlineKeyboardButton(text="🎲 Тағы бір сөз", callback_data="random_word")],
            ])
        )
        mark_learned(msg.from_user.id, kz)
        add_xp(msg.from_user.id, 5)
        return

    for kz, (en, cat) in DICT.items():
        if kz in text and len(kz) > 2:
            await msg.answer(
                f"{cat}\n\n🇰🇿 <b>{kz}</b>\n🇬🇧 <b>{en}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"🔊 Тыңдау: {kz} · {en}",
                        callback_data=f"w_pair_{kz}"
                    )],
                ])
            )
            return

    for en, (kz, cat) in DICT_EN.items():
        if en in text and len(en) > 2:
            await msg.answer(
                f"{cat}\n\n🇰🇿 <b>{kz}</b>\n🇬🇧 <b>{en}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"🔊 Тыңдау: {kz} · {en}",
                        callback_data=f"w_pair_{kz}"
                    )],
                ])
            )
            return

    await msg.answer(
        f"🤔 Кешіріңіз, «<b>{raw}</b>» сөзін таба алмадым.\n\n"
        f"💡 <b>Кеңес:</b>\n"
        f"  • 📖 <b>Сөздік</b> ашып, категория таңдаңыз\n"
        f"  • 🎲 <b>Кездейсоқ сөз</b> басыңыз\n"
        f"  • 🎮 <b>Викторина</b> ойнап көріңіз\n\n"
        f"🔗 Толық сөздік: {SITE_URL}",
        reply_markup=main_menu()
    )


async def run_bot():
    print("🤖 AI English Buddy v3.3 іске қосылды...")
    print(f"📖 Сөздікте {len(DICT)} сөз бар")
    print(f"📂 Категориялар: {len(CATEGORIES)}")
    print(f"🌐 Сайт: {SITE_URL}")
    print(f"🎙️ Голос KK: {VOICE_KK}")
    print(f"🎙️ Голос EN: {VOICE_EN}")
    print(f"💾 Кэш озвучки: {CACHE_DIR}")
    await dp.start_polling(bot)


@app.route('/')
def home():
    return "Bot is running"


@app.route('/health')
def health():
    return "OK"


def start_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN жоқ! Environment-те орнатыңыз.")

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    asyncio.run(run_bot())
