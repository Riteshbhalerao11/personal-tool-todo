"""Daily quote fetching from ZenQuotes API with offline fallback."""

import urllib.request
import json
import random
from datetime import datetime


FALLBACK_QUOTES = [
    {"text": "Imagination is more important than knowledge. Knowledge is limited. Imagination encircles the world.", "author": "Albert Einstein"},
    {"text": "Life is like riding a bicycle. To keep your balance, you must keep moving.", "author": "Albert Einstein"},
    {"text": "In the middle of difficulty lies opportunity.", "author": "Albert Einstein"},
    {"text": "Logic will get you from A to B. Imagination will take you everywhere.", "author": "Albert Einstein"},
    {"text": "Creativity is the greatest rebellion in existence.", "author": "Osho"},
    {"text": "Experience life in all possible ways - good-bad, bitter-sweet, dark-light. Experience all the dualities.", "author": "Osho"},
    {"text": "Be realistic: plan for a miracle.", "author": "Osho"},
    {"text": "The moment you accept yourself, you become beautiful.", "author": "Osho"},
    {"text": "Yesterday I was clever, so I wanted to change the world. Today I am wise, so I am changing myself.", "author": "Rumi"},
    {"text": "The wound is the place where the light enters you.", "author": "Rumi"},
    {"text": "What you seek is seeking you.", "author": "Rumi"},
    {"text": "Silence is the language of God, all else is poor translation.", "author": "Rumi"},
    {"text": "The first principle is that you must not fool yourself - and you are the easiest person to fool.", "author": "Richard Feynman"},
    {"text": "Nobody ever figures out what life is all about, and it doesn't matter. Explore the world.", "author": "Richard Feynman"},
    {"text": "The present is theirs; the future, for which I really worked, is mine.", "author": "Nikola Tesla"},
    {"text": "You have power over your mind - not outside events. Realize this, and you will find strength.", "author": "Marcus Aurelius"},
    {"text": "The happiness of your life depends upon the quality of your thoughts.", "author": "Marcus Aurelius"},
    {"text": "Waste no more time arguing about what a good man should be. Be one.", "author": "Marcus Aurelius"},
    {"text": "It is not that we have a short time to live, but that we waste a great deal of it.", "author": "Seneca"},
    {"text": "We suffer more often in imagination than in reality.", "author": "Seneca"},
    {"text": "The only way to make sense out of change is to plunge into it, move with it, and join the dance.", "author": "Alan Watts"},
    {"text": "This is the real secret of life - to be completely engaged with what you are doing in the here and now.", "author": "Alan Watts"},
    {"text": "A journey of a thousand miles begins with a single step.", "author": "Lao Tzu"},
    {"text": "Nature does not hurry, yet everything is accomplished.", "author": "Lao Tzu"},
    {"text": "When I let go of what I am, I become what I might be.", "author": "Lao Tzu"},
    {"text": "Somewhere, something incredible is waiting to be known.", "author": "Carl Sagan"},
    {"text": "We are a way for the cosmos to know itself.", "author": "Carl Sagan"},
    {"text": "He who has a why to live can bear almost any how.", "author": "Friedrich Nietzsche"},
    {"text": "One must still have chaos in oneself to be able to give birth to a dancing star.", "author": "Friedrich Nietzsche"},
    {"text": "The unexamined life is not worth living.", "author": "Socrates"},
    {"text": "Knowing yourself is the beginning of all wisdom.", "author": "Aristotle"},
    {"text": "No man is free who is not master of himself.", "author": "Epictetus"},
    {"text": "The mind is everything. What you think you become.", "author": "Buddha"},
    {"text": "Do not dwell in the past, do not dream of the future, concentrate the mind on the present moment.", "author": "Buddha"},
]


def fetch_quote_from_api():
    """Fetch today's quote from ZenQuotes API."""
    try:
        req = urllib.request.Request(
            'https://zenquotes.io/api/today',
            headers={'User-Agent': 'TodoWidget/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data and isinstance(data, list) and len(data) > 0:
                q = data[0]
                return {'text': q.get('q', ''), 'author': q.get('a', 'Unknown')}
    except Exception:
        pass
    return None


def get_daily_quote():
    """Get today's quote. Uses cache, then API, then fallback."""
    from lib.markdown_io import read_tracker, save_tracker

    tracker = read_tracker()
    today = datetime.now().strftime('%Y-%m-%d')

    # Return cached quote if it's from today
    if tracker.get('todayQuoteDate') == today and tracker.get('todayQuote'):
        return tracker['todayQuote']

    # Try API
    quote = fetch_quote_from_api()

    # Fallback to local collection
    if not quote:
        quote = random.choice(FALLBACK_QUOTES)

    # Cache it
    tracker['todayQuote'] = quote
    tracker['todayQuoteDate'] = today
    save_tracker(tracker)

    return quote


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
