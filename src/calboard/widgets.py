"""Small extras for the board: weather and word-of-the-day.

Both are free, keyless APIs (same Open-Meteo pattern used by the air-quality
project) and are cached so the board isn't re-fetching on every refresh.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Optional

import requests

_WEATHER_TTL = 900  # 15 min
_weather_cache: dict = {"at": 0.0, "data": None}

_WMO_ICON = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌦️",
    61: "🌧️", 63: "🌧️", 65: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "🌨️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}


def get_weather(lat: float, lon: float) -> Optional[dict]:
    now = time.time()
    if _weather_cache["data"] and now - _weather_cache["at"] < _WEATHER_TTL:
        return _weather_cache["data"]
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
            },
            timeout=8,
        )
        r.raise_for_status()
        j = r.json()
        code = j["current"]["weather_code"]
        data = {
            "temp": round(j["current"]["temperature_2m"]),
            "hi": round(j["daily"]["temperature_2m_max"][0]),
            "lo": round(j["daily"]["temperature_2m_min"][0]),
            "icon": _WMO_ICON.get(code, "🌡️"),
        }
        _weather_cache.update(at=now, data=data)
        return data
    except Exception as exc:  # noqa: BLE001 — a down weather API shouldn't blank the board
        print(f"calboard: weather fetch failed: {exc}")
        return _weather_cache["data"]  # serve stale data if we have it, else None


# A curated "worth learning" vocabulary list (not obscure jargon, not baby-basic) —
# a real random-word API happily hands back things like "sieverts" or plural nouns,
# which makes for a bad daily-learning card. One deterministic pick per calendar day,
# so the word is stable all day and doesn't repeat for ~a year.
#
# The free dictionary API below reliably supplies a real definition + pronunciation,
# but it almost never includes a usage example — so each word is paired here with one
# clean example sentence, written to illustrate that exact sense of the word.
_WORDS = {
    "luminous": "The full moon made the snow look luminous.",
    "ephemeral": "Cherry blossoms are ephemeral, lasting only a couple of weeks.",
    "serendipity": "Finding that old photo in a used book was pure serendipity.",
    "mellifluous": "Her mellifluous voice made the announcement easy to listen to.",
    "resilient": "Kids are often more resilient than we give them credit for.",
    "candid": "He gave a candid answer instead of the usual polite excuse.",
    "eloquent": "The best man gave a surprisingly eloquent toast.",
    "tenacious": "She was tenacious about finishing the marathon despite the rain.",
    "whimsical": "The treehouse had a whimsical design, all curved windows and bright paint.",
    "gregarious": "He's gregarious at parties but quiet one-on-one.",
    "meticulous": "The chef was meticulous about how each plate was arranged.",
    "vivacious": "Her vivacious personality lit up the whole room.",
    "audacious": "It was an audacious plan, but somehow it worked.",
    "buoyant": "The team stayed buoyant even after losing the first game.",
    "cascade": "Sunlight seemed to cascade through the kitchen window.",
    "diligent": "She's diligent about backing up her photos every week.",
    "effervescent": "His effervescent energy made even Monday mornings fun.",
    "fastidious": "He's fastidious about keeping his tools organized.",
    "gratitude": "We went around the table sharing one thing we felt gratitude for.",
    "harmonious": "The two colors made for a harmonious, calming palette.",
    "intrepid": "The intrepid hikers pushed on despite the storm warning.",
    "jubilant": "The crowd was jubilant when the home team scored.",
    "keen": "She has a keen eye for spotting a good deal.",
    "lucid": "After a good night's sleep, his thinking felt lucid again.",
    "magnanimous": "Even after winning, she was magnanimous toward her opponent.",
    "nostalgic": "The old song made him nostalgic for summers as a kid.",
    "opulent": "The hotel lobby was almost too opulent, all marble and gold.",
    "pensive": "She sat by the window, pensive, watching the rain.",
    "quaint": "The bakery had a quaint, old-fashioned charm to it.",
    "radiant": "The bride looked radiant walking down the aisle.",
    "solace": "He found solace in a quiet walk after a hard day.",
    "tranquil": "The lake was tranquil at dawn, barely a ripple.",
    "unwavering": "Her support for the idea stayed unwavering, even when others doubted it.",
    "vibrant": "The market was full of vibrant colors and smells.",
    "wistful": "He gave a wistful smile, thinking back to his college days.",
    "zealous": "The new volunteer was zealous about recycling everything possible.",
    "ambitious": "It's an ambitious goal, but not an impossible one.",
    "benevolent": "The benevolent landlord waived the late fee without being asked.",
    "captivate": "The magician managed to captivate the entire room of kids.",
    "demure": "She gave a demure nod instead of answering out loud.",
    "elated": "He was elated when the acceptance letter finally arrived.",
    "flourish": "Her small business really began to flourish after the second year.",
    "genuine": "His apology felt genuine, not just something he had to say.",
    "humble": "Despite the award, she stayed humble about her work.",
    "idyllic": "The cabin by the lake was about as idyllic as it gets.",
    "jovial": "Grandpa's always in a jovial mood around the holidays.",
    "kindred": "They felt like kindred spirits from the moment they met.",
    "lavish": "The wedding was a lavish, three-day celebration.",
    "mirthful": "The kids' mirthful laughter carried through the whole house.",
    "nurture": "It takes time to nurture a habit until it sticks.",
    "optimistic": "She stayed optimistic about the move, even during the packing chaos.",
    "pristine": "He kept the old car in pristine condition for thirty years.",
    "quintessential": "A rainy weekend and a good book — the quintessential Sunday.",
    "resolute": "He stayed resolute about quitting sugar, even at the birthday party.",
    "sincere": "Her thank-you note felt short but sincere.",
    "thrive": "The new plant seems to thrive on the kitchen windowsill.",
    "unassuming": "The chef was unassuming despite running the best kitchen in town.",
    "vigilant": "New parents learn to stay vigilant, even while half-asleep.",
    "wholesome": "It was a wholesome, simple family dinner — nothing fancy.",
    "amiable": "The new neighbor seems amiable and easy to talk to.",
    "brisk": "They took a brisk walk before breakfast to wake up.",
    "cordial": "The two rivals stayed cordial, even after the tough game.",
    "dauntless": "The dauntless toddler tried the big slide on her first visit.",
    "earnest": "His earnest effort to learn the recipe finally paid off.",
    "frugal": "Being frugal for a year let them afford the trip.",
    "graceful": "The dancer made the difficult move look graceful and easy.",
    "hopeful": "She stayed hopeful about the test results all week.",
    "invigorate": "A cold morning swim always seems to invigorate him.",
    "jaunty": "He wore a jaunty little hat to the picnic.",
    "kinetic": "The lobby had a huge kinetic sculpture that never stopped moving.",
    "lighthearted": "It was a lighthearted argument about which movie to watch.",
    "meander": "The trail meanders along the creek for a couple of miles.",
    "nimble": "You need nimble fingers to play that piano piece well.",
    "obliging": "The obliging waiter swapped her order without any fuss.",
    "placid": "The lake stayed placid all afternoon, perfect for kayaking.",
    "quirky": "Their apartment has a quirky charm, like the crooked bookshelf.",
    "robust": "The old bridge is still remarkably robust after all these years.",
    "steadfast": "He remained steadfast in his plan to run the marathon.",
    "thoughtful": "It was a thoughtful gift — she'd clearly been paying attention.",
    "upbeat": "She stayed upbeat about the delayed flight, oddly enough.",
    "valiant": "It was a valiant attempt, even though the cake collapsed.",
    "wander": "We let ourselves wander through the old part of town.",
    "yearn": "After the move, she began to yearn for her old neighborhood.",
    "zest": "He added the lemon zest right at the end for brightness.",
    "articulate": "The kid gave a surprisingly articulate answer for a six-year-old.",
    "blissful": "They spent a blissful weekend doing absolutely nothing.",
    "curious": "The cat stayed curious about the empty box for hours.",
    "delightful": "Dinner turned into a delightful, three-hour conversation.",
    "empathy": "She listened with real empathy instead of jumping to advice.",
    "forthright": "He was forthright about the delay instead of making excuses.",
    "genial": "The new manager has a genial, easygoing way about him.",
    "hearty": "They came in from the cold to a hearty bowl of soup.",
    "immerse": "She likes to immerse herself in a new language before visiting.",
    "jubilee": "The town threw a jubilee to mark its hundredth year.",
    "kaleidoscope": "Autumn turned the hillside into a kaleidoscope of color.",
    "lively": "The market was lively on Saturday morning, full of music.",
    "modest": "He gave a modest shrug when asked about the award.",
    "novel": "It's a novel way to solve a problem we've had for years.",
    "ornate": "The old theater had an ornate ceiling covered in gold leaf.",
    "playful": "The puppy gave a playful nudge to get attention.",
    "quicken": "Her pace began to quicken as she neared the finish line.",
    "reverie": "He was pulled from his reverie by the ringing phone.",
    "spirited": "It was a spirited debate, but a friendly one.",
    "tender": "She gave the bruised plant some tender care and it recovered.",
    "unfazed": "He seemed unfazed by the chaos in the kitchen.",
    "vivid": "She still has a vivid memory of her first day of school.",
    "warmth": "There was real warmth in the way she welcomed new neighbors.",
    "amicable": "They kept things amicable even after deciding to go separate ways.",
    "brave": "It was brave of him to speak up in the meeting.",
    "cheerful": "The barista's cheerful greeting made the wait feel shorter.",
    "devoted": "He's endlessly devoted to that scruffy old dog.",
    "exuberant": "The kids gave an exuberant welcome when Dad walked in.",
    "fond": "She's grown fond of her morning walk around the block.",
    "grand": "It wasn't a grand gesture, just a note left on the counter.",
    "honest": "An honest mistake is easier to forgive than an excuse.",
    "inspire": "Her garden really did inspire the whole street to plant more flowers.",
    "joyful": "It was a small, joyful gathering with just close friends.",
}

_word_cache: dict = {"day": None, "data": None}


def get_word_of_day() -> Optional[dict]:
    today = date.today()
    if _word_cache["day"] == today and _word_cache["data"]:
        return _word_cache["data"]
    words = list(_WORDS.keys())
    start = today.toordinal() % len(words)
    try:
        # Try today's pick, then walk forward deterministically if a lookup ever fails.
        for offset in range(len(words)):
            word = words[(start + offset) % len(words)]
            dr = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=8)
            if dr.status_code != 200:
                continue
            entry = dr.json()[0]
            meaning = entry["meanings"][0]
            definition = meaning["definitions"][0]
            # Prefer a real pronunciation from the `phonetics` list — the top-level
            # `phonetic` field is often blank even when one is available there.
            phonetic = entry.get("phonetic") or next(
                (p.get("text") for p in entry.get("phonetics", []) if p.get("text")), ""
            )
            data = {
                "word": entry.get("word", word),
                "phonetic": phonetic,
                "part_of_speech": meaning.get("partOfSpeech", ""),
                "definition": definition.get("definition", ""),
                "example": definition.get("example") or _WORDS[word],
            }
            _word_cache.update(day=today, data=data)
            return data
    except Exception as exc:  # noqa: BLE001 — a down word API shouldn't blank the board
        print(f"calboard: word-of-day fetch failed: {exc}")
    return _word_cache["data"]  # serve yesterday's word rather than nothing


_recipe_cache: dict = {"day": None, "data": None}


def get_recipe_of_day() -> Optional[dict]:
    """A real meal suggestion (TheMealDB, free/keyless), stable for the whole day."""
    today = date.today()
    if _recipe_cache["day"] == today and _recipe_cache["data"]:
        return _recipe_cache["data"]
    try:
        r = requests.get("https://www.themealdb.com/api/json/v1/1/random.php", timeout=8)
        r.raise_for_status()
        meal = r.json()["meals"][0]
        ingredients = []
        for i in range(1, 21):
            name = (meal.get(f"strIngredient{i}") or "").strip()
            if not name:
                continue
            measure = (meal.get(f"strMeasure{i}") or "").strip()
            ingredients.append(f"{measure} {name}".strip())
        data = {
            "name": meal["strMeal"],
            "thumb": meal.get("strMealThumb", ""),
            "category": meal.get("strCategory") or "",
            "area": meal.get("strArea") or "",
            "youtube": meal.get("strYoutube") or "",
            "ingredients": ingredients[:6],
        }
        _recipe_cache.update(day=today, data=data)
        return data
    except Exception as exc:  # noqa: BLE001 — a down recipe API shouldn't blank the board
        print(f"calboard: recipe-of-day fetch failed: {exc}")
    return _recipe_cache["data"]  # serve yesterday's pick rather than nothing
