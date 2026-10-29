"""Run `python selftest.py`. Checks all the logic offline: no Google, no AI, no internet."""
import sys, re, time, types, urllib.error, io

import generate as G
sheetio = compose = research = llmmod = generate = G
names = G.names
Verifier = G.Verifier


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
    assert len(s) <= 40 and s == s.strip(), s
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
assert len(o.grid[1][2]) <= 40 and o.grid[1][2] == o.grid[1][2].rstrip(" ,;:-.&"), o.grid[1][2]
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
mw, _, _ = sheetio.open_book(FakeBook([FakeWS("Ready to Send", [["Email"]]), FakeWS("Leads", [["Email"]])]))
assert mw.title == "Leads", "robot tabs must never be picked as master automatically"
__import__("os").environ["MASTER_TAB"] = "Ready to Send"
try:
    sheetio.open_book(FakeBook([FakeWS("Ready to Send", [["Email"]]), FakeWS("Leads")])); raise SystemExit("robot tab as master")
except SystemExit as e:
    assert "MASTER_TAB" in str(e)
__import__("os").environ.pop("MASTER_TAB")
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
assert len(fs) <= 40 and not fs.endswith(" "), fs
assert compose.fit_subject("Supercalifragilisticexpialidocious-and-more-words-here-now") .__len__() <= 40
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

# ================= 9. AI layer: aliases, fallbacks, failover =================
def http(code, body=b""):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(body))

time.sleep = lambda s: None
os_env = __import__("os").environ
for k in list(os_env):
    if re.search(r"(GEMINI|GROQ|OPENROUTER|YOUTUBE|ZEROBOUNCE)_", k):
        del os_env[k]

# 9a. key aliases: both names work, duplicates removed, quotes/whitespace cleaned
os_env["GEMINI_API_KEY"] = ' "g1" , g2\n'
os_env["GEMINI_KEY"] = "g2,g3"
os_env["GROQ_API_KEY"] = "q1"
os_env["OPENROUTER_KEY"] = "o1"
os_env["YOUTUBE_API_KEY"] = "yt1"
os_env["ZEROBOUNCE_API_KEY"] = "zb1"
assert G.env_keys("GEMINI_KEY", "GEMINI_API_KEY") == ["g2", "g3", "g1"], G.env_keys("GEMINI_KEY", "GEMINI_API_KEY")
assert G.env("YOUTUBE_KEY", "YOUTUBE_API_KEY") == "yt1" and G.env("ZEROBOUNCE_KEY", "ZEROBOUNCE_API_KEY") == "zb1"
# no model name is read from the environment any more: keys only, models are discovered and tested
_orig = (G._gemini_call, G._openai_style_call, G.list_gemini_models, G.list_groq_models, G.list_openrouter_models)
probed = []
def fake_call(key, model, system, user):
    probed.append((key, model))
    if model == "dead-model":
        raise G.BadModel()
    if model == "no-quota":
        raise G.QuotaOut()
    return '{"ok": true}'
G._gemini_call = fake_call
G._openai_style_call = lambda url, h: fake_call
G.list_gemini_models = lambda k: ["no-quota", "dead-model", "gem-a", "gem-b", "gem-c"]
G.list_groq_models = lambda k: ["groq-big", "groq-small"]
G.list_openrouter_models = lambda k: ["or-free"]
os_env["GEMINI_MODEL"] = "gemini-3.8-flash, llama-3.3-70b-versatile"; os_env["GROQ_MODEL"] = "my-groq"; os_env["OPENROUTER_MODEL"] = "my/or"
L = G.llm_from_env()
assert [p.name for p in L.providers] == ["Gemini", "Gemini", "Gemini", "Groq", "OpenRouter"], [p.name for p in L.providers]
assert L.providers[0].models == ["gem-a", "gem-b"], L.providers[0].models     # dead + no-quota models skipped by the test
assert all(m not in ("gemini-3.8-flash", "my-groq", "my/or") for _, m in probed), "model variables must be ignored"
assert L.providers[3].models == ["groq-big", "groq-small"] and L.providers[4].models == ["or-free"]
# a key the provider rejects is skipped, the others still work
def bad_key_call(key, model, system, user):
    if key == "g2": raise G.BadKey()
    return '{"ok": true}'
G._gemini_call = bad_key_call
L = G.llm_from_env()
assert [(p.name, p.keys) for p in L.providers if p.name == "Gemini"] == [("Gemini", ["g3"]), ("Gemini", ["g1"])]
# if listing models fails, the built-in guesses are tested instead
G._gemini_call = fake_call; G.list_gemini_models = lambda k: []
L = G.llm_from_env()
assert L.providers[0].models[0] == "gemini-flash-latest", L.providers[0].models
# if nothing answers at all: a clear stop, not a hang
G._gemini_call = lambda *a: (_ for _ in ()).throw(G.QuotaOut())
G._openai_style_call = lambda url, h: (lambda *a: (_ for _ in ()).throw(G.QuotaOut()))
try:
    G.llm_from_env(); raise SystemExit("dead keys accepted")
except SystemExit as e:
    assert "start-up test" in str(e), e
for k in ("GEMINI_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_KEY"):
    del os_env[k]
try:
    G.llm_from_env(); raise SystemExit("no key accepted")
except SystemExit as e:
    assert "GEMINI_KEY" in str(e) and "GROQ_KEY" in str(e) and "OPENROUTER_KEY" in str(e)
for k in ("GEMINI_MODEL", "GROQ_MODEL", "OPENROUTER_MODEL"):
    del os_env[k]
G._gemini_call, G._openai_style_call, G.list_gemini_models, G.list_groq_models, G.list_openrouter_models = _orig

# 9b. error classification
C = G.classify
assert isinstance(C(429), G.RateLimit) and isinstance(C(404), G.BadModel) and isinstance(C(401), G.BadKey)
assert isinstance(C(403), G.BadKey) and isinstance(C(402), G.BadKey) and isinstance(C(503), G.ServerErr)
assert isinstance(C(400, "API key not valid. Please pass a valid API key"), G.BadKey)
assert isinstance(C(400, "model_decommissioned"), G.BadModel) and isinstance(C(500, ""), G.ServerErr)
assert isinstance(C(400, "RESOURCE_EXHAUSTED"), G.RateLimit)
assert isinstance(C(429, "quota exceeded ... limit: 0, model: gemini-2.5-pro"), G.QuotaOut)
assert isinstance(C(429, "GenerateRequestsPerDayPerProjectPerModel-FreeTier".lower()), G.QuotaOut)
assert isinstance(C(429, "perminuteperprojectpermodel"), G.RateLimit)

# 9c. a model that dies mid-run (404) or has no quota is dropped ONCE and the next model answers
calls = []
def gem_call(key, model, system, user):
    calls.append((key, model))
    if model == "m-retired":
        raise G.BadModel()
    if model == "m-nodaily":
        raise G.QuotaOut()
    return '{"subject": "s", "body": "b"}'
prov = G.Provider("Gemini", ["k1"], ["m-retired", "m-nodaily", "m-good"], gem_call)
L = G.LLM([prov])
assert L.ask("s", "u") == {"subject": "s", "body": "b"}
assert [m for _, m in calls] == ["m-retired", "m-nodaily", "m-good"], calls
assert L.ask("s", "u") == {"subject": "s", "body": "b"} and [m for _, m in calls].count("m-retired") == 1
# the run deadline stops waiting instead of hanging
L2 = G.LLM([G.Provider("Gemini", ["k"], ["m"], lambda *a: (_ for _ in ()).throw(G.RateLimit()))], deadline=time.time() - 1)
try:
    L2.ask("s", "u"); raise SystemExit("deadline ignored")
except G.Exhausted:
    pass

# 9d. rank_gemini_models: stable before preview, flash before pro, junk removed
items = [{"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
         {"name": "models/gemini-3-flash-preview", "supportedGenerationMethods": ["generateContent"]},
         {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
         {"name": "models/gemini-2.5-flash-image", "supportedGenerationMethods": ["generateContent"]},
         {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
         {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
         {"name": "models/gemini-live-x", "supportedGenerationMethods": ["generateContent"]},
         {"name": "models/other-model", "supportedGenerationMethods": ["generateContent"]}]
assert G.rank_gemini_models(items) == ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite", "gemini-2.5-pro"], G.rank_gemini_models(items)
items.append({"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]})
assert G.rank_gemini_models(items)[0] == "gemini-flash-latest"

# 9e. Gemini rate-limited -> Groq answers; Groq down -> OpenRouter; discovered models keep Gemini's priority
log_calls = []
def g_rl(key, model, s, u):
    log_calls.append("G"); raise G.RateLimit()
def q_ok(key, model, s, u):
    log_calls.append("Q"); return '{"from": "groq"}'
def o_ok(key, model, s, u):
    log_calls.append("O"); return '{"from": "openrouter"}'
def q_bad(key, model, s, u):
    log_calls.append("Q"); raise G.BadKey()
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], g_rl), G.Provider("Groq", ["k"], ["m"], q_ok), G.Provider("OpenRouter", ["k"], ["m"], o_ok)])
assert L.ask("s", "u") == {"from": "groq"} and log_calls == ["G", "Q"]
log_calls.clear()
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], g_rl), G.Provider("Groq", ["k"], ["m"], q_bad), G.Provider("OpenRouter", ["k"], ["m"], o_ok)])
assert L.ask("s", "u") == {"from": "openrouter"} and log_calls == ["G", "Q", "O"], log_calls
assert L.ask("s", "u") == {"from": "openrouter"}, "dead Groq key must stay off"
assert L.used == {"OpenRouter": 2}

# 9f. quota exhaustion on EVERYTHING -> Exhausted (and only then)
def always_rl(key, model, s, u):
    raise G.RateLimit()
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], always_rl), G.Provider("Groq", ["k"], ["m"], always_rl)])
try:
    L.ask("s", "u"); raise SystemExit("should be exhausted")
except G.Exhausted:
    pass
# one working provider among failures is enough
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], always_rl), G.Provider("Groq", ["k"], ["m"], q_ok)])
assert L.ask("s", "u") == {"from": "groq"}
# server errors: switch away, then switch off after repeated failures
def srv(key, model, s, u):
    raise G.ServerErr("503")
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], srv), G.Provider("Groq", ["k"], ["m"], q_ok)])
assert L.ask("s", "u") == {"from": "groq"}
# garbage JSON is a Transient (caller retries), it must NOT kill the provider
n = {"i": 0}
def flaky(key, model, s, u):
    n["i"] += 1
    return "not json at all" if n["i"] == 1 else '{"ok": 1}'
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], flaky)])
try:
    L.ask("s", "u"); raise SystemExit("bad json accepted")
except G.Transient:
    pass
assert L.ask("s", "u") == {"ok": 1}
assert G.parse_json('```json\n{"a": 1}\n```') == {"a": 1} and G.parse_json('noise {"a": 1} trailing') == {"a": 1}

# 9g. key rotation inside one provider
seen_keys = []
def rot(key, model, s, u):
    seen_keys.append(key)
    if key == "k1":
        raise G.RateLimit()
    return '{"ok": 1}'
L = G.LLM([G.Provider("Gemini", ["k1", "k2"], ["m"], rot)])
assert L.ask("s", "u") == {"ok": 1} and seen_keys == ["k1", "k2"]

# 9h. whole pipeline survives a dead primary provider (end to end through run())
class Chain(FakeLLM):
    """FakeLLM text, but delivered through a real LLM failover chain."""
    pass
def ok_via_groq(key, model, system, user):
    ans = FakeLLM().ask(system, user)
    return json.dumps(ans)
import json
L = G.LLM([G.Provider("Gemini", ["k"], ["m"], g_rl), G.Provider("Groq", ["k"], ["m"], ok_via_groq)])
m, o, l = make([lead("x@x.com", "Xylo Channel", "", "5", "Vid", "notes")])
st = go(m, o, l, L)
assert st["written"] == 1 and o.grid[1][0] == "x@x.com" and L.used == {"Groq": 1}

# 9i. master tab: "Main" is the default, header row is found, explicit wrong name is an error
def tabs(*sheets):
    return G.FakeBook(sheets) if hasattr(G, "FakeBook") else FakeBook(list(sheets))
os_env.pop("MASTER_TAB", None)
a = FakeWS("Other", [["Email"], ["a@a.co"]]); mn = FakeWS("Main", [["Email", "Name"], ["b@b.co", "Bo"]])
mw, ow, lw = G.open_book(FakeBook([a, mn]))
assert mw.title == "Main"
mw, ow, lw = G.open_book(FakeBook([a]))                       # no "Main": first non-robot tab, with a note
assert mw.title == "Other"
os_env["MASTER_TAB"] = "Nope"
try:
    G.open_book(FakeBook([a, mn])); raise SystemExit("bad MASTER_TAB accepted")
except SystemExit as e:
    assert "not found" in str(e) and "Main" in str(e)
os_env.pop("MASTER_TAB")
mm = G.Master(FakeWS("Main", [["Leads export"], ["", "Email", "Channel"], ["", "q@q.co", "Q Chan"]]))
assert mm.rows[0]["Email"] == "q@q.co" and mm.rows[0]["Channel"] == "Q Chan" and mm.rows[0]["_row"] == 3



# 9j. the real HTTP layer, with a mocked network
class Resp:
    def __init__(self, obj): self.b = json.dumps(obj).encode()
    def read(self, *a): return self.b
    def __enter__(self): return self
    def __exit__(self, *a): return False
sent = []
def fake_urlopen(req, timeout=0):
    sent.append(req)
    h = fake_urlopen.handler
    r = h(req)
    if isinstance(r, Exception):
        raise r
    return Resp(r)
G.urllib.request.urlopen = fake_urlopen

# Gemini: key goes in a header (never the URL), thought parts are ignored, JSON mode requested
fake_urlopen.handler = lambda req: {"candidates": [{"content": {"parts": [{"text": "hidden", "thought": True}, {"text": '{"a": 1}'}]}}]}
txt = G._gemini_call("SECRETKEY", "gemini-x", "sys", "usr")
rq = sent[-1]
assert txt == '{"a": 1}' and "SECRETKEY" not in rq.full_url and rq.get_header("X-goog-api-key") == "SECRETKEY"
assert "gemini-x:generateContent" in rq.full_url and json.loads(rq.data)["generationConfig"]["responseMimeType"] == "application/json"
fake_urlopen.handler = lambda req: {"promptFeedback": {"blockReason": "SAFETY"}}
try:
    G._gemini_call("k", "m", "s", "u"); raise SystemExit("blocked reply accepted")
except G.Transient:
    pass
fake_urlopen.handler = lambda req: http(404, b'{"error": {"message": "models/gemini-1.5-flash is not found"}}')
try:
    G._gemini_call("k", "gemini-1.5-flash", "s", "u"); raise SystemExit("404 not detected")
except G.BadModel:
    pass
fake_urlopen.handler = lambda req: http(429, b'{"error": {"status": "RESOURCE_EXHAUSTED"}}')
try:
    G._gemini_call("k", "m", "s", "u"); raise SystemExit("429 not detected")
except G.RateLimit:
    pass
fake_urlopen.handler = lambda req: urllib.error.URLError("boom")
try:
    G._gemini_call("k", "m", "s", "u"); raise SystemExit("network error not detected")
except G.ServerErr:
    pass

# Groq style: a model that refuses JSON mode is retried once without it
groq = G._openai_style_call("https://api.groq.com/openai/v1/chat/completions", {})
modes = []
def groq_h(req):
    p = json.loads(req.data); modes.append("response_format" in p)
    if "response_format" in p:
        return http(400, b'{"error": {"message": "json mode is not supported with this model"}}')
    return {"choices": [{"message": {"content": '{"ok": 1}'}}]}
fake_urlopen.handler = groq_h
assert groq("gk", "llama", "s", "u") == '{"ok": 1}' and modes == [True, False]
assert sent[-1].get_header("Authorization") == "Bearer gk"
# OpenRouter: HTTP 200 carrying an error body is still treated as the error it is
fake_urlopen.handler = lambda req: {"error": {"code": 429, "message": "Rate limit exceeded"}}
try:
    groq("k", "m", "s", "u"); raise SystemExit("200-with-error not detected")
except G.RateLimit:
    pass
fake_urlopen.handler = lambda req: {"error": {"code": 402, "message": "Insufficient credits"}}
try:
    groq("k", "m", "s", "u"); raise SystemExit("402 not detected")
except G.BadKey:
    pass
fake_urlopen.handler = lambda req: {"choices": []}
try:
    groq("k", "m", "s", "u"); raise SystemExit("empty choices accepted")
except G.Transient:
    pass


# live model discovery through the real code path (re-create the real function from source)
src = open(__file__.replace("selftest.py", "generate.py"), encoding="utf-8").read()
ns = {}
exec("import json, re, urllib.request, urllib.error, urllib.parse\n" +
     src[src.index("class RateLimit"):src.index("def _gemini_call")] +
     "GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models'\n" +
     src[src.index("def _http"):src.index("def _gemini_call")] +
     src[src.index("def rank_gemini_models"):src.index("class Combo")], ns)
fake_urlopen.handler = lambda req: {"models": [{"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
                                               {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]}]}
assert ns["list_gemini_models"]("k") == ["gemini-3.5-flash"]
fake_urlopen.handler = lambda req: http(403, b"")
assert ns["list_gemini_models"]("k") == [], "discovery must never raise"


# 9k. main() end to end: env aliases -> providers -> verification -> research -> AI over (mocked) HTTP -> sheet
def net(req):
    u = req.full_url
    if "dns.google" in u:
        return {"Status": 0, "Answer": [{"type": 15, "data": "10 mx.example.org."}]}
    if "generativelanguage" in u:
        if "gemini-down" in u:
            return http(404, b"")                                        # configured model is retired
        if u.endswith("/models?pageSize=200"):
            return {"models": [{"name": "models/gemini-9-flash", "supportedGenerationMethods": ["generateContent"]}]}
        usr = json.loads(req.data)["contents"][0]["parts"][0]["text"]
        if "Channel:" not in usr:                                         # the start-up test message
            return {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}
        ch = re.search(r"^Channel: (.*)$", usr, re.M).group(1)
        vid = re.search(r"^Latest videos: (.*)$", usr, re.M)
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(
            {"subject": "Quick idea for " + ch[:20], "body": good_body(ch, vid.group(1).split(" | ")[0] if vid else None),
             "facts_used": [ch], "first_name": ""})}]}}]}
    return http(500, b"")
fake_urlopen.handler = net
env_ = __import__("os").environ
env_.update({"GEMINI_API_KEY": "gk", "GEMINI_MODEL": "gemini-down", "YOUTUBE_API_KEY": "", "RUN_LIMIT": "2",
             "WRITE_PAUSE": "0", "ZEROBOUNCE_API_KEY": ""})
m, o, l = make([lead("a1@example.org", "Alpha Channel One", "", "9", "V1", "notes a"),
                lead("a2@example.org", "Beta Channel Two", "", "8", "V2", "notes b"),
                lead("a3@example.org", "Gamma Channel Three", "", "7", "V3", "notes c")])
G.open_book = lambda book=None: (m, o, l)
G.main()
assert [r[0] for r in o.grid[1:]] == ["a1@example.org", "a2@example.org"], "RUN_LIMIT=2 must write exactly 2"
assert all(r[3].endswith("Best regards,") for r in o.grid[1:]) and m.writes == 0
G.main()                                                         # next run picks up the third lead only
assert [r[0] for r in o.grid[1:]] == ["a1@example.org", "a2@example.org", "a3@example.org"]
G.main()                                                         # nothing left: no changes, no crash
assert len(o.grid) == 4
# DRY_RUN writes no rows
m, o, l = make([lead("d1@example.org", "Delta Channel", "", "9", "V1", "n")])
G.open_book = lambda book=None: (m, o, l)
env_["DRY_RUN"] = "yes"; G.main(); env_.pop("DRY_RUN")
assert len(o.grid) == 1 and len(l.grid) == 1, "dry run must not write rows or log lines"
for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "YOUTUBE_API_KEY", "RUN_LIMIT", "WRITE_PAUSE", "ZEROBOUNCE_API_KEY"):
    env_.pop(k, None)

# ================= 10. names =================
assert names.from_cell("Muhammad Zubair") == "Zubair" and names.from_cell("Fit With Mike Studio") == ""
assert names.from_cell("john123") == "" and names.from_cell("Mike & Sara") == ""
assert names.email_source("john123@x.com") == "" and names.email_source("ayesha.khan@x.com") == "ayesha khan"
src = names.build_sources({"Channel name": "Explore with James"}, "ayesha.khan@x.com")
assert names.accept("James", src) == "James" and names.accept("Ayesha", src) == "Ayesha"
assert names.accept("Explore", src) == "" and names.accept("Zubair", src) == "" and names.accept("Muhammad", "Muhammad Ali") == ""

print("All checks passed.")
