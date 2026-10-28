"""Run `python selftest.py`. Checks all the logic offline: no Google, no AI, no internet."""
import sys, re, time, types, urllib.error, io

import sheetio, compose, names, research, llm as llmmod, generate
from verify import Verifier


# ---------------- a fake Google Sheet ----------------
class FakeWS:
    def __init__(self, title, grid=None):
        self.title, self.grid, self.row_count = title, grid or [], max(len(grid or []), 1000)
        self.writes = 0

    def _c(self, s):
        n = 0
        for ch in s:
            n = n * 26 + ord(ch) - 64
        return n

    def get_all_values(self):
        w = max((len(r) for r in self.grid), default=0)
        return [list(r) + [""] * (w - len(r)) for r in self.grid]

    def get(self, rng):
        m = re.fullmatch(r"([A-Z]+)(\d*):([A-Z]+)(\d*)", rng)
        c0, c1 = self._c(m.group(1)), self._c(m.group(3))
        r0 = int(m.group(2) or 1)
        r1 = int(m.group(4) or len(self.grid))
        out = []
        for i in range(r0 - 1, min(r1, len(self.grid))):
            row = (self.grid[i] + [""] * c1)[c0 - 1:c1]
            while row and row[-1] == "":
                row.pop()
            out.append(row)
        while out and not out[-1]:
            out.pop()
        return out

    def update(self, values, range_name, raw=None):
        assert raw is True, "must write raw text (never parsed as formulas)"
        m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", range_name)
        c0, r0 = self._c(m.group(1)), int(m.group(2))
        assert len(values) == int(m.group(4)) - r0 + 1, "range size does not match data"
        self.writes += 1
        for i, row in enumerate(values):
            while len(self.grid) < r0 + i:
                self.grid.append([])
            line = self.grid[r0 + i - 1]
            while len(line) < c0 + len(row) - 1:
                line.append("")
            for j, v in enumerate(row):
                line[c0 + j - 1] = v

    def add_rows(self, n):
        self.row_count += n


class FakeBook:
    def __init__(self, sheets):
        self.sheets = sheets

    def worksheets(self):
        return list(self.sheets)

    def add_worksheet(self, title, rows, cols):
        w = FakeWS(title)
        self.sheets.append(w)
        return w


class FakeYT:
    off = False

    def info(self, url):
        return None


def good_body(channel, video=None):
    v = f' and your video "{video}"' if video else ""
    return (f"I came across {channel}{v}. A lot of channels at this stage find that editing eats the hours "
            "they would rather spend filming.\n\nI am a video editor and motion designer who helps channels get more "
            "out of every upload. I can cut a 30 to 60 second sample from one of your own clips, so you can judge the "
            "style before deciding anything.\n\nCould you reply with a clip or a video link?")


class FakeLLM:
    """Pretends to be the AI. mode lets a test make it misbehave."""

    def __init__(self, mode="good"):
        self.mode, self.calls = mode, 0

    def ask(self, system, user):
        self.calls += 1
        ch = re.search(r"^Channel: (.*)$", user, re.M).group(1)
        vid = re.search(r"^Latest videos: (.*)$", user, re.M)
        vid = vid.group(1).split(" | ")[0] if vid else None
        low = "LOW_DATA: yes" in user
        if self.mode == "exhausted":
            raise llmmod.Exhausted("x")
        if self.mode == "invented":
            return {"subject": "Quick idea", "body": good_body(ch).replace("30 to 60", "500"), "facts_used": [ch], "first_name": ""}
        if self.mode == "greeting":
            return {"subject": "Quick idea for you and your channel", "body": "Hi Sara,\n\n" + good_body(ch, vid) + "\n\nBest regards,\nChris",
                    "facts_used": [] if low else [ch], "first_name": ""}
        if self.mode == "longsubject":
            return {"subject": "A really quite long subject line that goes way past the limit",
                    "body": good_body(ch, None if low else vid), "facts_used": [] if low else [ch], "first_name": ""}
        name = "James" if "James" in ch else ("Zubair" if "Zubair" in user else "")
        return {"subject": "Quick idea for " + ch[:20], "body": good_body(ch, None if low else vid),
                "facts_used": [] if low else [ch], "first_name": name}


HDR = ["Niche", "Score", "Channel", "Url", "Email", "Name", "Website", "Latest Video", "Notes", "Active", "Status", "My Notes"]


def lead(email, channel="", name="", score="50", video="", notes="", active="", status="", niche="Vlogs"):
    d = dict(Niche=niche, Score=score, Channel=channel, Url="", Email=email, Name=name, Website="", **{"Latest Video": video},
             Notes=notes, Active=active, Status=status, **{"My Notes": "SECRET PRIVATE"})
    return [d[h] for h in HDR]


def make(rows):
    return FakeWS("Leads", [list(HDR)] + rows), FakeWS("Ready to Send"), FakeWS("Log")


research.fetch = lambda url: ("", [])            # never touch the internet in tests
ver = lambda: Verifier(check_mx=False)


def go(m, o, l, llm=None, limit=25, **kw):
    return generate.run(m, o, l, llm or FakeLLM(), FakeYT(), ver(), limit, time.time() + 600, **kw)


# ================= 1. first run =================
rows = [lead("Sara@Daily.com ", "Daily Frames", "Sara Lee", "90", "How I Plan a Week of Shorts", "Posts weekly Shorts tutorials"),
        lead("james@x.com", "Explore with James", "", "80", "Hiking 101", "Travel and hiking"),
        lead("zubair@x.com", "ZB Edits", "Muhammad Zubair", "70", "My Setup", "Gear reviews"),
        lead("not an email", "Broken", "", "60"),
        lead("sara@daily.com", "Daily Frames 2", "", "55"),                   # duplicate of row 1
        lead("off@x.com", "Dead Channel", "", "50", active="No"),
        lead("stop@x.com", "Opted Out", "", "50", status="Stop"),
        lead("", "", ""),                                                     # empty row
        lead("lowdata@x.com", "Tiny Channel", "", "10", "", "")]
m, o, l = make(rows)
master_before = [list(r) for r in m.grid]
st = go(m, o, l)
assert m.grid == master_before, "MASTER TAB WAS MODIFIED"
assert m.writes == 0
assert o.grid[0] == ["Email", "Name", "Subject", "Body"], o.grid[0]
body = {r[0]: r for r in o.grid[1:]}
assert set(body) == {"sara@daily.com", "james@x.com", "zubair@x.com", "lowdata@x.com"}, set(body)
assert [r[0] for r in o.grid[1:]][0] == "sara@daily.com", "highest Score must come first"
assert body["sara@daily.com"][1] == "Sara" and body["james@x.com"][1] == "James" and body["zubair@x.com"][1] == "Zubair"
assert body["lowdata@x.com"][1] == "Team", "no name found must be Team"
for em, (e, n, s, b) in body.items():
    assert len(s) <= 45 and s == s.strip(), s
    assert b.endswith("Best regards,") and b == b.rstrip() and b.count("Best regards,") == 1
    assert not re.match(r"(?i)\s*(hi|hello|dear|hey)\b", b) and not b.startswith(n)
    assert b.rstrip().splitlines()[-3] == 'Not Interested, Reply "Unsub".'
    assert "Level Up" not in b and "SECRET" not in b
    assert all(len(r) == 4 for r in o.grid), "exactly four columns"
assert st["written"] == 4 and st["skipped"] >= 4, st
assert body["lowdata@x.com"][3].count('"') == 2, "low-data email must not quote a video"
logt = [r for r in l.grid[1:]]
res = {(r[1], r[2]) for r in logt}
assert ("not an email", "skipped - invalid email") in res and ("sara@daily.com", "skipped - duplicate in master") in res
assert ("off@x.com", "skipped - inactive") in res and ("sara@daily.com", "written") in res
assert any("low data" in r[3] for r in logt if r[2] == "written")

# ================= 2. rerun = no duplicates, no log growth =================
n_o, n_l = len(o.grid), len(l.grid)
st = go(m, o, l)
assert len(o.grid) == n_o and len(l.grid) == n_l and st["written"] == 0, "rerun created duplicates or log noise"

# ================= 3. YOUR Date / follow-up columns are never touched =================
o.grid[0] += ["Date", "Follow-up 1"]
for r in o.grid[1:]:
    r += ["28 Oct", ""]
snapshot_E = [(r[4], r[5]) for r in o.grid]
m.grid.append(lead("new1@x.com", "Fresh One", "", "99", "Fresh Video", "Notes here"))
m.grid.append(lead("new2@x.com", "Fresh Two", "", "98", "Other Video", "More notes"))
go(m, o, l)
assert [(r[4], r[5]) for r in o.grid[:len(snapshot_E)]] == snapshot_E, "Date columns were changed"
assert [r[0] for r in o.grid[-2:]] == ["new1@x.com", "new2@x.com"], "new rows must be appended below"
assert len(o.grid[-1]) == 4, "the robot must write A-D only"

# ================= 4. you delete sent rows: they are NOT regenerated =================
del o.grid[1:3]
go(m, o, l)
assert "sara@daily.com" not in [r[0] for r in o.grid], "a deleted (already sent) row came back"

# ================= 5. you SORT the output tab: still safe =================
o.grid[1:] = sorted(o.grid[1:], key=lambda r: r[0], reverse=True)
m.grid.append(lead("new3@x.com", "Fresh Three", "", "50", "V3", "n3"))
go(m, o, l)
assert o.grid[-1][0] == "new3@x.com" and len([r for r in o.grid if r[0] == "new3@x.com"]) == 1

# ================= 6. AI misbehaves =================
m, o, l = make([lead("a@x.com", "Alpha Channel", "", "5", "Vid", "notes")])
go(m, o, l, FakeLLM("greeting"))
assert o.grid[1][2] and not re.match(r"(?i)\s*hi", o.grid[1][3]) and "Chris" not in o.grid[1][3], "greeting/sign-off not stripped"
m, o, l = make([lead("a@x.com", "Alpha Channel", "", "5", "Vid", "notes")])
go(m, o, l, FakeLLM("longsubject"))
assert len(o.grid[1][2]) <= 45 and o.grid[1][2] == o.grid[1][2].rstrip(" ,;:-.&"), o.grid[1][2]
m, o, l = make([lead("a@x.com", "Alpha Channel", "", "5", "Vid", "notes")])
fl = FakeLLM("invented")
for _ in range(4):
    st = go(m, o, l, fl)
assert len(o.grid) == 1 and st["failed"] == 0, "after 3 failures the lead must be skipped, not retried forever"
assert sum(1 for r in l.grid if r[2] == "failed") == 3 and any(r[2] == "gave up" for r in l.grid)
m, o, l = make([lead(f"e{i}@x.com", f"Channel Number{i}x", "", str(100 - i), f"Vid{i}", "n") for i in range(6)])
class Dying(FakeLLM):
    def ask(self, s, u):
        if self.calls >= 3:
            raise llmmod.Exhausted("x")
        return super().ask(s, u)
st = go(m, o, l, Dying())
assert st["stopped_early"] and len(o.grid) == 4, "quota stop must save the finished rows"   # header + 3

# ================= 7. odd header / tab problems =================
m, o, l = make([lead("a@x.com", "A Channel", "", "1", "V", "n")])
o.grid = [["Emails", "Names", "Subject Lines", "Bodies", "Date"]]
go(m, o, l); assert o.grid[0][4] == "Date" and o.grid[1][0] == "a@x.com"
o.grid = [["Foo", "Bar", "x", "y"]]
try:
    go(m, o, l); raise SystemExit("wrong header accepted")
except SystemExit as e:
    assert "not Email, Name, Subject, Body" in str(e)
try:
    sheetio.open_book(FakeBook([FakeWS("Ready to Send", [["Email"]]), FakeWS("Leads")])); raise SystemExit("robot tab as master")
except SystemExit as e:
    assert "MASTER_TAB" in str(e)
mw, ow, lw = sheetio.open_book(FakeBook([FakeWS("Leads", [["Email"], ["a@b.co"]])]))
assert mw.title == "Leads" and ow.title == "Ready to Send" and lw.title == "Log"
try:
    sheetio.Master(FakeWS("x", [["Foo", "Bar"]])); raise SystemExit("no email col accepted")
except SystemExit as e:
    assert "no Email column" in str(e)

# big batch grows the grid
m, o, l = make([lead(f"b{i}@x.com", f"Chan Numbr{i}", "", "1", f"Vid{i}", "n") for i in range(12)])
o.row_count = 3
go(m, o, l, limit=12); assert o.row_count >= 13 and len(o.grid) == 13

# YouTube + website facts reach the AI context (and private columns never do)
class YT2:
    off = False
    def info(self, url):
        return {"title": "Daily Frames", "description": "I am Sara and I make film tutorials", "videos": ["Lighting 101", "Color Grading Basics"]}
research.fetch = lambda url: ("Welcome to my site about cinematic lighting", [])
lead_d = {h: "" for h in sheetio.ALIASES}; lead_d.update(Url="https://youtube.com/@daily", Website="dailyframes.com", Notes="Notes line", Niche="Film")
cx, ns, fn, inf = research.build_context(lead_d, YT2())
assert "Lighting 101" in cx and "cinematic lighting" in cx and "Notes line" in cx and fn >= 3 and inf["channel"] == "Daily Frames"
assert "I am Sara" in ns["Channel description"]
research.fetch = lambda url: ("", [])

# ================= 8. compose rules =================
assert compose.clean_core("Hi Sara, I came across X?\n\nBest regards,\nChris") == "I came across X?"
assert compose.clean_core("Hello,\n\nFirst line.\nCould you send a clip?\n\nThanks!\nBest") == "First line.\nCould you send a clip?"
assert compose.final_body("Hello there?").endswith("Not Interested, Reply \"Unsub\".\n\nBest regards,")
assert compose.final_body("X?", optout=False) == "X?\n\nBest regards,"
fs = compose.fit_subject("Quick idea for your editing workflow and more")
assert len(fs) <= 45 and not fs.endswith(" "), fs
assert compose.fit_subject("Supercalifragilisticexpialidocious-and-more-words-here-now") .__len__() <= 45
ctx = "Channel: Daily Frames\nLatest videos: How I Plan a Week of Shorts"
core = good_body("Daily Frames", "How I Plan a Week of Shorts")
ok = lambda **kw: compose.check(kw.get("s", "Quick idea"), kw.get("c", core), kw.get("f", ["Daily Frames"]), ctx, "Daily Frames", False, kw.get("r", set()))
assert ok() == ""
assert ok(s="WHY NOT TRY THIS NOW") == "subject is all capitals"
assert ok(s="Re: hello") == "subject starts with Re/Fwd"
assert ok(c=core.replace("30 to 60", "500")) == "number is not in the data"
assert ok(c=core.replace("How I Plan a Week of Shorts", "How I Quit My Job")) == "quoted text is not in the data"
assert ok(c=core.replace("I am a video", "We are a video")) .startswith("must be one person")
assert ok(c=core.replace("I am a video", "At Level Up VFX I am a video")) == "mentions the company name"
assert ok(c="Hi Sara, " + core) == "starts with a greeting"
assert ok(c=core.replace("I came across", "I watched")) == "claims to have watched or read"
assert ok(c=core + " Visit https://x.com") == "link, placeholder or markdown"
assert ok(c=core + "\n\nThanks for your time.") == "ask must be the last line"
assert ok(f=["Made up"]) == "fact not in data"
assert ok(r={" ".join(compose.norm(core).split()[:5])}) == "opening is the same as another email"
assert ok(c=core.replace("Daily Frames", "Other Place")) .startswith("channel name missing")
good_row = ["a@b.co", "Sara", "Hi there", compose.final_body("Q?")]
assert compose.validate_final(good_row) == ""
assert compose.validate_final(["a@b.co", "Sara", "Hi", "Q?\n\nBest regards, "]) != ""
assert compose.validate_final(["A@b.co", "Sara", "Hi", "Q?\n\nBest regards,"]) == "bad email"
assert compose.validate_final(["a@b.co", "john123", "Hi", "Q?\n\nBest regards,"]) == "bad name"
assert compose.validate_final(["a@b.co", "Team", "x" * 46, "Q?\n\nBest regards,"]) == "bad subject"
assert sheetio.no_formula("=SUM(A1)") == "SUM(A1)" and sheetio.no_formula("- a") == "a"
assert research.safe("WOW!! 100% FREE $$ https://x.co \U0001F525 title") == "WOW 100 FREE title"

# ================= 9. AI providers: key rotation, quota =================
def http(code):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b""))
calls = []
def build(key, model, system, user):
    calls.append(key)
    if key == "k1":
        raise http(429)
    return '```json\n{"subject": "s", "body": "b"}\n```'
time.sleep = lambda s: None
p = llmmod.Provider("T", ["k1", "k2"], "m", build)
assert llmmod.LLM([p]).ask("s", "u") == {"subject": "s", "body": "b"} and calls == ["k1", "k2"]
p = llmmod.Provider("T", ["k1"], "m", build)
try:
    llmmod.LLM([p]).ask("s", "u"); raise SystemExit("should be exhausted")
except llmmod.Exhausted:
    pass
def bad(key, model, system, user):
    raise http(404)
p1 = llmmod.Provider("A", ["x"], "m", bad); p2 = llmmod.Provider("B", ["y"], "m", lambda *a: '{"ok": 1}')
assert llmmod.LLM([p1, p2]).ask("s", "u") == {"ok": 1}, "must fall back to the next provider"
assert llmmod.parse_json('noise {"a": 1} trailing') == {"a": 1}

# ================= 10. names =================
assert names.from_cell("Muhammad Zubair") == "Zubair" and names.from_cell("Fit With Mike Studio") == ""
assert names.from_cell("john123") == "" and names.from_cell("Mike & Sara") == ""
assert names.email_source("john123@x.com") == "" and names.email_source("ayesha.khan@x.com") == "ayesha khan"
src = names.build_sources({"Channel name": "Explore with James"}, "ayesha.khan@x.com")
assert names.accept("James", src) == "James" and names.accept("Ayesha", src) == "Ayesha"
assert names.accept("Explore", src) == "" and names.accept("Zubair", src) == "" and names.accept("Muhammad", "Muhammad Ali") == ""

print("All checks passed.")
