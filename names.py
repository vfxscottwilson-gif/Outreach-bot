"""First-name helper. The AI proposes a first name; this file checks the proposal before it is used.
A name is accepted only if it is really written in the lead's own data (name column, channel name, channel
description, website, notes, or a 'first.last' email address). Anything else becomes "Team"."""
import re

TEAM = "Team"

# "Muhammad" is a title-like first word, not the name people go by: "Muhammad Zubair" -> Zubair.
SKIP_PREFIX = {"muhammad", "mohammad", "mohammed", "muhammed", "mohamed", "muhamad", "mohamad", "mohd", "md", "mhd"}

# Words that are never a person's first name (channel words, roles, filler).
NOT_NAMES = {"team", "official", "channel", "tv", "vlog", "vlogs", "vlogger", "studio", "studios", "media", "films",
             "film", "gaming", "games", "gamer", "plays", "tech", "tips", "daily", "life", "world", "show", "the",
             "with", "and", "for", "by", "from", "my", "our", "your", "mr", "mrs", "ms", "dr", "info", "contact",
             "hello", "business", "admin", "support", "sales", "mail", "email", "office", "inquiries", "enquiries",
             "booking", "bookings", "management", "mgmt", "production", "productions", "creative", "creations",
             "digital", "online", "network", "music", "podcast", "news", "learn", "learning", "academy", "school",
             "kids", "family", "fitness", "travel", "cooking", "kitchen", "recipes", "explore", "adventures",
             "vfx", "editor", "editing", "video", "videos", "youtube", "youtuber", "creator", "content", "brand",
             "hub", "lab", "labs", "zone", "land", "club", "co", "inc", "ltd", "llc", "group", "company", "shop",
             "store", "design", "designs", "art", "arts", "fashion", "beauty", "health", "wellness", "yoga",
             "food", "foodie", "review", "reviews", "reviewer", "unboxing", "tutorial", "tutorials", "how", "best",
             "top", "new", "pro", "plus", "max", "king", "queen", "boss", "master", "guru", "expert", "coach",
             "frames", "motion", "clips", "shorts", "reels", "stories", "story", "journey", "diary", "life"}
TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "coach", "captain", "pastor", "rev"}
JOINERS = {"and", "&", "+", "/", "with", "x"}


def _letters(s):
    return "".join(ch for ch in str(s or "") if ch.isalpha() or ch in "'\u2019-").strip("-'\u2019")


def _tidy(name):
    return name[:1].upper() + name[1:].lower() if name.isupper() or name.islower() else name


def _ok_shape(name):
    low = name.lower()
    return 2 <= len(name) <= 20 and low not in SKIP_PREFIX and low not in NOT_NAMES


def from_cell(cell):
    """First name from a 'Name' cell you typed. '' if the cell looks like a brand or a group, not one person."""
    text = re.sub(r"\([^)]*\)", " ", str(cell or ""))
    if re.search(r"\d|[&+/@,_]|\band\b", text, re.I):      # digits or handle characters: not a real name
        return ""
    toks = [t for t in (_letters(w) for w in text.split()) if t]
    toks = [t for t in toks if t.lower().rstrip(".") not in TITLES]
    if not toks or len(toks) > 3:
        return ""
    if any(t.lower() in NOT_NAMES and t.lower() not in SKIP_PREFIX for t in toks):
        return ""                                     # "Explore With James" is not a clean name cell
    while len(toks) > 1 and toks[0].lower() in SKIP_PREFIX:
        toks.pop(0)                                   # Muhammad Zubair -> Zubair
    name = toks[0]
    return _tidy(name) if _ok_shape(name) else ""


def email_source(email):
    """'sara.johnson@x.com' -> 'sara johnson'. Only a clean first.last pattern counts. 'john123' or 'info' never do."""
    local = str(email or "").split("@")[0].lower()
    parts = re.split(r"[._\-]", local)
    if len(parts) == 2 and all(p.isalpha() and len(p) >= 2 for p in parts) and parts[0] not in NOT_NAMES \
            and parts[0] not in SKIP_PREFIX:
        return " ".join(parts)
    return ""


def build_sources(name_src, email):
    """The only text the AI may use to look for a first name."""
    lines = [f"{k}: {v}" for k, v in name_src.items() if str(v).strip()]
    e = email_source(email)
    if e:
        lines.append(f"Email address: {e}")
    return "\n".join(lines)


def accept(candidate, sources, avoid=""):
    """Returns a clean first name, or "" if the AI's guess is not safe to use."""
    if re.search(r"\d|@|_", str(candidate or "")):
        return ""
    name = _letters(candidate)
    if not _ok_shape(name):
        return ""
    low = name.lower()
    if avoid and re.search(r"(?<![^\W\d_])" + re.escape(low) + r"(?![^\W\d_])", avoid.lower()):
        return ""                                     # the word is also their niche/topic, so it is not a name
    found = False
    for line in str(sources).splitlines():
        for m in re.finditer(r"(?<![^\W\d_])" + re.escape(low) + r"(?![^\W\d_])", line, re.I):
            # written with a capital letter, or the line has no capitals at all (all lower case: cannot tell)
            if m.group(0)[:1].isupper() or not re.search(r"[A-Z]", line.split(":", 1)[-1]):
                found = True
    return _tidy(name) if found else ""
