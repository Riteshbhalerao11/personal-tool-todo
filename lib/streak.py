"""Streak calculation + tracker.json management."""

from datetime import datetime, timedelta
from lib.markdown_io import read_todo_sections, read_tracker, save_tracker


MILESTONES = {
    7: "One whole week! Building a habit!",
    14: "Two weeks strong!",
    21: "21 days - habit formed!",
    30: "A full month! Unstoppable.",
    50: "50 days of pure dedication!",
    75: "75 days! Three quarters to 100!",
    100: "TRIPLE DIGITS! 100 days!",
    150: "150 days! Elite tier.",
    200: "200 days! Almost a year!",
    365: "ONE FULL YEAR! Legend!",
}


def update_streak():
    """Recalculate streak from todo sections. Returns streak info dict."""
    sections = read_todo_sections()
    tracker = read_tracker()

    # Build set of active dates (days with at least one completed item)
    active_dates = set()
    for s in sections:
        for item in s['items']:
            if item['done']:
                active_dates.add(s['date'])
                break

    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    streak = 0

    if today_str in active_dates:
        streak = 1
        d = today - timedelta(days=1)
    else:
        yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        if yesterday_str in active_dates:
            streak = 0
            d = today - timedelta(days=1)
        else:
            tracker['currentStreak'] = 0
            save_tracker(tracker)
            return {
                'current': 0,
                'longest': int(tracker.get('longestStreak', 0)),
                'broken': True,
                'milestone': None,
            }

    # Count consecutive days backward
    while True:
        ds = d.strftime('%Y-%m-%d')
        if ds in active_dates:
            streak += 1
            d -= timedelta(days=1)
        else:
            break

    tracker['currentStreak'] = streak
    if streak > int(tracker.get('longestStreak', 0)):
        tracker['longestStreak'] = streak
    tracker['lastActiveDate'] = today_str
    save_tracker(tracker)

    milestone = MILESTONES.get(streak)

    return {
        'current': streak,
        'longest': int(tracker.get('longestStreak', 0)),
        'broken': False,
        'milestone': milestone,
    }


def get_streak_display():
    info = update_streak()
    if info['broken']:
        return "Streak broken - time for a comeback!"
    if info['current'] == 0:
        return "Complete a task to start your streak!"
    text = f"{info['current']} Day Streak!"
    if info['milestone']:
        text += f" {info['milestone']}"
    return text
