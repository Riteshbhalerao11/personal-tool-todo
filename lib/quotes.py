"""Quote rotation (3/day via ZenQuotes) + Poem of the Day (PoetryDB)."""

import random
import re
from datetime import datetime

import requests


ZENQUOTES_URL = "https://zenquotes.io/api/quotes"
POETRYDB_RANDOM_URL = "https://poetrydb.org/random/10"
POEMHUNTER_BASE = "https://www.poemhunter.com/poem/"


def get_current_period():
    """Return current period: 'morning' (00-08), 'day' (08-16), 'evening' (16-24)."""
    hour = datetime.now().hour
    if hour < 8:
        return 'morning'
    elif hour < 16:
        return 'day'
    else:
        return 'evening'


def _slugify(title):
    """Convert a poem title into a PoemHunter URL slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def _fetch_zenquotes():
    """Fetch ~50 quotes from ZenQuotes API."""
    try:
        resp = requests.get(ZENQUOTES_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [
            {"text": q["q"], "author": q["a"]}
            for q in data
            if q.get("q") and q.get("a") and q["a"] != "zenquotes.io"
        ]
    except Exception:
        return None


def fetch_poem_of_day():
    """Fetch a poem from PoetryDB, picking one with a displayable length (5-60 lines)."""
    try:
        resp = requests.get(POETRYDB_RANDOM_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Pick a poem with reasonable length for display
        for p in data:
            lines = p.get("lines", [])
            if 5 <= len(lines) <= 60 and p.get("title") and p.get("author"):
                slug = _slugify(p["title"])
                return {
                    "title": p["title"],
                    "author": p["author"],
                    "lines": lines,
                    "url": f"{POEMHUNTER_BASE}{slug}/",
                }
        # If no poem in the sweet spot, take the shortest one > 2 lines
        candidates = [p for p in data if len(p.get("lines", [])) > 2
                       and p.get("title") and p.get("author")]
        if candidates:
            best = min(candidates, key=lambda p: len(p["lines"]))
            slug = _slugify(best["title"])
            return {
                "title": best["title"],
                "author": best["author"],
                "lines": best["lines"][:60],
                "url": f"{POEMHUNTER_BASE}{slug}/",
            }
    except Exception:
        pass
    return None


def get_daily_quote():
    """Get quote for current time period. Changes 3 times a day."""
    from lib.markdown_io import read_tracker, save_tracker

    tracker = read_tracker()
    today = datetime.now().strftime('%Y-%m-%d')
    period = get_current_period()
    cache_key = f"{today}_{period}"

    # Return cached quote if it matches current period
    if tracker.get('quotePeriodKey') == cache_key and tracker.get('periodQuote'):
        return tracker['periodQuote']

    # --- Quotes pool ---
    quotes_pool = tracker.get('quotesPool', [])
    if len(quotes_pool) < 3 or tracker.get('quotesPoolDate') != today:
        new_quotes = _fetch_zenquotes()
        if new_quotes:
            quotes_pool = new_quotes
            tracker['quotesPool'] = quotes_pool
            tracker['quotesPoolDate'] = today

    # Select from pool using seeded random (deterministic per period)
    rng = random.Random(cache_key)
    if quotes_pool:
        quote = rng.choice(quotes_pool)
    else:
        quote = {"text": "The best time to plant a tree was 20 years ago. The second best time is now.", "author": "Chinese Proverb"}

    result = {"text": quote["text"], "author": quote["author"]}

    # Cache it
    tracker['periodQuote'] = result
    tracker['quotePeriodKey'] = cache_key
    # Clean up old cache keys from previous versions
    tracker.pop('todayQuote', None)
    tracker.pop('todayQuoteDate', None)
    tracker.pop('poetryPool', None)
    tracker.pop('poetryPoolDate', None)
    save_tracker(tracker)

    return result


def get_poem_of_day():
    """Get poem of the day, cached for the whole day."""
    from lib.markdown_io import read_tracker, save_tracker

    tracker = read_tracker()
    today = datetime.now().strftime('%Y-%m-%d')

    if tracker.get('poemOfDayDate') == today and tracker.get('poemOfDay'):
        return tracker['poemOfDay']

    poem = fetch_poem_of_day()
    if poem:
        tracker['poemOfDay'] = poem
        tracker['poemOfDayDate'] = today
        save_tracker(tracker)

    return poem


def get_time_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return random.choice([
            "Good morning, sunshine!",
            "Rise and grind!",
            "Morning! Fresh start, fresh mind.",
            "New day. New energy.",
            "Top of the morning!",
        ])
    elif 12 <= hour < 17:
        return random.choice([
            "Good afternoon! Keep the momentum.",
            "Afternoon - you are doing great.",
            "Halfway through the day!",
            "Afternoon focus mode.",
        ])
    elif 17 <= hour < 21:
        return random.choice([
            "Good evening! Wrapping up?",
            "Evening - time to wind down.",
            "Hope you had a great day!",
            "Almost done for the day!",
        ])
    else:
        return random.choice([
            "Burning the midnight oil?",
            "Late night productivity hits different.",
            "Night owl mode activated.",
            "The quiet hours - prime focus time.",
        ])
