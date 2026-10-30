"""A short quote for the morning message, a different one each day (the list cycles)."""
from __future__ import annotations

from datetime import date

QUOTES = [
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("It always seems impossible until it's done.", "Nelson Mandela"),
    ("Well done is better than well said.", "Benjamin Franklin"),
    ("Do what you can, with what you have, where you are.", "Theodore Roosevelt"),
    ("Small deeds done are better than great deeds planned.", "Peter Marshall"),
    ("Energy and persistence conquer all things.", "Benjamin Franklin"),
    ("The future depends on what you do today.", "Mahatma Gandhi"),
    ("You miss 100% of the shots you don't take.", "Wayne Gretzky"),
    ("Action is the foundational key to all success.", "Pablo Picasso"),
    ("Quality is not an act, it is a habit.", "Aristotle"),
    ("Discipline is the bridge between goals and accomplishment.", "Jim Rohn"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("Arise, awake, and stop not till the goal is reached.", "Swami Vivekananda"),
    ("You have a right to your actions, never to their fruits.", "Bhagavad Gita"),
    ("Opportunities multiply as they are seized.", "Sun Tzu"),
    ("He who has a why to live can bear almost any how.", "Friedrich Nietzsche"),
    ("What we think, we become.", "Buddha"),
    ("Fortune favors the bold.", "Virgil"),
    ("I am not afraid of storms, for I am learning how to sail my ship.", "Louisa May Alcott"),
    ("The best way out is always through.", "Robert Frost"),
    ("Dream big. Start small. Act now.", "Robin Sharma"),
    ("Success is the sum of small efforts, repeated day in and day out.", "Robert Collier"),
    ("A year from now you may wish you had started today.", "Karen Lamb"),
    ("Hard work beats talent when talent doesn't work hard.", "Tim Notke"),
    ("If you're going through hell, keep going.", "Winston Churchill"),
    ("Excellence is never an accident.", "Aristotle"),
    ("Strive for progress, not perfection.", "Unknown"),
    ("Make each day your masterpiece.", "John Wooden"),
    ("The harder I work, the luckier I get.", "Samuel Goldwyn"),
    ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
    ("Never mistake motion for action.", "Ernest Hemingway"),
    ("We are what we repeatedly do.", "Will Durant"),
    ("You can't use up creativity. The more you use, the more you have.", "Maya Angelou"),
    ("Whatever you are, be a good one.", "Abraham Lincoln"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Simplicity is prerequisite for reliability.", "Edsger Dijkstra"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Stay hungry, stay foolish.", "Steve Jobs"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
]


def quote_for(day: date) -> tuple[str, str]:
    return QUOTES[day.toordinal() % len(QUOTES)]
