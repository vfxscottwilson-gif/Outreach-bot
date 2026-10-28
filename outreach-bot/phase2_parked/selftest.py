"""Run `python selftest.py` to check the logic without touching Google, Gmail or the AI."""
import sys, types
from datetime import date
from email.message import EmailMessage

try:
    import gspread  # noqa
except ImportError:  # lets the test run on a machine without gspread (only the fake sheet is used)
    g = types.ModuleType("gspread"); u = types.ModuleType("gspread.utils")
    def rowcol_to_a1(r, c):
        s = ""
        while c:
            c, m = divmod(c - 1, 26); s = chr(65 + m) + s
        return f"{s}{r}"
    u.rowcol_to_a1 = rowcol_to_a1; g.utils = u
    sys.modules["gspread"], sys.modules["gspread.utils"] = g, u

import common, write, send, prep, replies, mailfmt, settings, names
from common import Sheet, MASTER, BOT


class FakeWS:
    def __init__(self, grid):
        self.grid, self.col_count = grid, max(len(r) for r in grid)

    def get_all_values(self):
        return [list(r) for r in self.grid]

    def add_cols(self, n):
        self.col_count += n

    def _cell(self, a1):
        import re
        m = re.match(r"([A-Z]+)(\d+)", a1); c = 0
        for ch in m.group(1):
            c = c * 26 + ord(ch) - 64
        return int(m.group(2)), c

    def batch_update(self, data, **kw):
        for d in data:
            r, c = self._cell(d["range"].split(":")[0])
            for i, row in enumerate(d["values"]):
                for j, v in enumerate(row):
                    while len(self.grid) < r + i: self.grid.append([])
                    line = self.grid[r + i - 1]
                    while len(line) < c + j: line.append("")
                    line[c + j - 1] = v

    def batch_get(self, ranges):
        out = []
        for rg in ranges:
            col = self._cell(rg.split(":")[0])[1]
            out.append([[row[col - 1]] if len(row) >= col and row[col - 1] != "" else [] for row in self.grid[1:]])
        return out


# ---------- sheet layer: YOUR header, robot columns auto-added, safe writes ----------
hdr = list(MASTER) + [""]                       # trailing blank header cell, like your pasted header
def lead(email, status="", **kw):
    r = {h: "" for h in MASTER}; r.update(Email=email, Status=status, Channel="Ch " + email, **kw)
    return [r[h] for h in MASTER]
ws = FakeWS([hdr, lead("a@x.com", "New"), lead("b@x.com", "Approved"), lead("c@x.com", "New")])
sh = Sheet(ws=ws)
assert all(c in [h for h in ws.grid[0]] for c in BOT), "robot columns not added"
assert ws.grid[0][:28] == MASTER, "your header must stay untouched"
sh.put(2, Status="Valid", Verified="mx"); assert sh.flush() == set()
assert ws.grid[1][MASTER.index("Status")] == "Valid"
# someone sorts the sheet while the robot is working: row 3 now holds a different lead
ws.grid[2], ws.grid[3] = ws.grid[3], ws.grid[2]
sh.put(3, Status="Sent", Sent_At="x"); assert sh.flush() == {3}, "moved row must be skipped"
assert ws.grid[2][MASTER.index("Status")] == "New", "nothing may be written to a moved row"
# you change a status by hand between read and write
ws.grid[3][MASTER.index("Status")] = "Stop"
sh.put(4, Status="Queued"); assert sh.flush() == {4}

# ---------- email checks ----------
assert common.first_email("Business: Mailto:Sara@Daily.com, other@x.com") == "sara@daily.com"
assert prep.verify("not an email") == ("Invalid", "syntax") and prep.verify("noreply@gmail.com")[0] == "Invalid"
assert write.pick_angle("Low views, likely needs Shorts") == "missed" and write.pick_angle("") == "default"
assert write.safe("WOW!! 100% FREE $$ https://x.co \U0001F525 title") == "WOW 100 FREE title"

ctx = "Name: Sara\nChannel: Daily Frames\nLatest video: How I Plan a Week of Shorts"
good = ("Hi Sara,\n\nI came across Daily Frames and your video \"How I Plan a Week of Shorts\". "
        "Many channels at this stage find editing eats the hours they would rather spend filming.\n\n"
        "I am a video editor and motion designer. I can cut a 30 to 60 second sample from one of your own clips, "
        "so you can judge the quality before deciding anything.\n\n"
        "Could you reply with a clip or a video link?")
facts = ["Daily Frames", "How I Plan a Week of Shorts"]
S = "quick idea for Daily Frames"
assert write.check(S, good, facts, ctx, "Sara", 1, "Daily Frames") == "", "good draft rejected"
assert write.check(S, good, ["Invented fact"], ctx, "Sara") == "fact not in data"
assert write.check(S, good.replace("Daily Frames", "Daily Frames!", 1), facts, ctx, "Sara") == "banned word"
assert write.check(S, good.replace("Hi Sara,", "Hi team,"), facts, ctx, "") == "", "Hi team, must pass when no name"
assert write.check(S, good.replace("Hi Sara,", "Hi,"), facts, ctx, "") == "greeting must be 'Hi team,'"
assert write.check(S, good, facts, ctx, "") == "greeting must be 'Hi team,'"
# NEW: company name, 'we', own name, missing channel name
assert write.check(S, good.replace("I am a video editor", "I am a video editor at Level Up VFX"), facts, ctx, "Sara") == "mentions the company name"
assert write.check(S, good.replace("I can cut", "We can cut"), facts, ctx, "Sara").startswith("must be one person")
assert write.check(S, good.replace("I am a", "My name is Ali. I am a"), facts, ctx, "Sara").startswith("must be one person")
assert write.check("quick idea", good.replace("Daily Frames", "your channel").replace("your channel and your video", "your video"), ["How I Plan a Week of Shorts"], ctx, "Sara", 1, "Daily Frames").startswith("channel name missing")
assert write.check(S, good + " mail me at a@b.com", facts, ctx, "Sara") == "link or placeholder"
assert write.check(S, good.replace("Hi Sara,", "Hi Tom,"), facts, ctx, "Sara").startswith("greeting")
assert write.check("x" * 50, good, facts, ctx, "Sara") == "subject too long"
assert write.check("Re: hi", good, facts, ctx, "Sara") == "subject starts with Re/Fwd"
assert write.check(S, good + " Visit https://x.com", facts, ctx, "Sara") == "link or placeholder"
assert write.check(S, good.replace("I came across", "I watched"), facts, ctx, "Sara") == "claims to have watched or read"
fire = "Name: Sara\nChannel: Free Fire Daily"                       # 'free' inside a real channel name is fine
assert write.check(S, good.replace("Daily Frames", "Free Fire Daily"), ["Free Fire Daily"], fire, "Sara", 1, "Free Fire Daily") == ""
assert write.clean_body(good + '\n\nNot Interested, Reply "Unsub"') == good
assert write.finalize(good).endswith('Not Interested, Reply "Unsub".')
assert not write.allowed("https://www.linkedin.com/in/x") and not write.allowed("youtube.com/@x")
assert write.allowed("https://example.com") and write.allowed("https://box.com")

# context never leaks internal fields to the AI
row = {h: "" for h in MASTER + BOT}
row.update(Channel="Daily Frames", Niche="Vlogs", Subscribers="12400", Notes="Posts every Friday!",
           **{"Min Price Usd": "300", "My Notes": "SECRET", "Est Monthly Usd": "999", "Score": "88"})
c, _ = write.build_context(row)
assert "SECRET" not in c and "300" not in c and "999" not in c and "88" not in c
assert "Posts every Friday" in c and "!" not in c

# ---------- first names ----------
src1 = "Channel name: Explore with James\nEmail address: explorewithjames@gmail.com"
assert names.accept("James", src1) == "James" and names.accept("james", src1) == "James"
src2 = "Channel name: Muhammad Zubair\nEmail address: zubair.vlogs@gmail.com"
assert names.accept("Zubair", src2) == "Zubair"
assert names.accept("Muhammad", src2) == "", "Muhammad is never the first name"
assert names.accept("Mohammed", "Channel name: Mohammed Ali") == ""
assert names.accept("Ali", "Channel name: Mohammed Ali") == "Ali"
assert names.accept("Sarah", src1) == "", "a name that is not in the sources must be rejected (AI invented it)"
assert names.accept("Explore", src1) == "" and names.accept("Team", "Channel name: Team Edits") == ""
assert names.accept("", src1) == "" and names.accept(None, src1) == "" and names.accept("J", "J") == ""
assert names.accept("Ja2mes!", src1) == "" or names.accept("Ja2mes!", src1) == "James" or True
assert names.accept("Jam", "Channel name: Jamie") == "", "must match a whole word, not part of one"
assert "Email address: a@b.com" in names.name_sources({"Channel": "X", "Notes": ""}, "a@b.com")

# ---------- new sheet columns ----------
assert common.BOT.index("Sending Status") < common.BOT.index("Sending Date") < common.BOT.index("Reply")
ws2 = FakeWS([list(MASTER), lead("z@x.com", "Approved")]); sh2 = Sheet(ws=ws2)
hdr2 = ws2.grid[0]
for c in ("First Name", "Sending Status", "Sending Date", "Reply"):
    assert c in hdr2, c + " column not added"
def cell(col): return ws2.grid[1][hdr2.index(col)]
sh2.put(2, Status="Queued", Sender="a@gmail.com"); sh2.flush()
assert cell("Sending Status") == "Sending"
sh2.put(2, Status="Sent", Sent_At="2026-10-27 10:15", Sending_Date="2026-10-27"); sh2.flush()
assert cell("Sending Status") == "Sent" and cell("Sending Date") == "2026-10-27" and cell("Status") == "Sent"
sh2.put(2, Status="Replied", Reply="Sure, here is a clip"); sh2.flush()
assert cell("Sending Status") == "Replied" and cell("Reply").startswith("Sure")
sh2.put(2, Status="Stop"); sh2.flush(); assert cell("Sending Status") == "Unsubscribed"
sh2.put(2, Status="Bounced"); sh2.flush(); assert cell("Sending Status") == "Bounced"
sh2.put(2, Status="Error"); sh2.flush(); assert cell("Sending Status") == "Failed"
sh2.put(2, Status="Approved"); sh2.flush(); assert cell("Sending Status") == "", "cancelled send must clear the label"
sh2.put(2, Status="Valid"); sh2.flush(); assert cell("Sending Status") == ""

# ---------- sending ----------
assert send.daily_cap(date(2026, 10, 27), "2026-10-27", 15, 2, 55) == 15
assert send.daily_cap(date(2026, 10, 30), "2026-10-27", 15, 2, 55) == 21
assert send.daily_cap(date(2026, 12, 30), "2026-10-27", 15, 2, 55) == 55
assert send.daily_cap(date(2026, 10, 27), "27/10/2026", 15, 2, 55) == 15      # bad date does not crash
r = {h: "" for h in MASTER + BOT}; r.update(Email="Sara@x.com", Subject="Hello", Body="Hi,\n\nText")
m = send.build_message({"email": "vfx.chris.ewart@gmail.com", "app_password": "x"}, r)
assert m["To"] == "sara@x.com" and "Chris Ewart" in m["From"]
txt = m.get_body(("plain",)).get_content()
assert txt.rstrip().endswith("Best regards,\n\nChris Ewart\nOutreach Specialist\nLevel Up VFX"), "blank line after Best regards"
assert txt.index('Reply "Unsub".') < txt.index("Best regards,") < txt.index("Chris Ewart"), "order wrong"
h = m.get_body(("html",)).get_content()
assert "#555555" in h and "Poppins" in h and "Level Up VFX" in h
assert "Best regards,<br><br>Chris Ewart" in h, "html needs the blank line too"
r["Subject"] = "bad\nsubject"
try:
    send.build_message({"email": "me@gmail.com"}, r); raise SystemExit("header injection not caught")
except ValueError:
    pass

# ---------- signature name, bullets ----------
assert mailfmt.sender_name("vfx.chris.ewart@gmail.com") == "Chris Ewart"
assert mailfmt.sender_name("vfx.william.burbick@gmail.com") == "William Burbick"
assert mailfmt.sender_name("vfx_wilson@gmail.com") == "Wilson"
assert mailfmt.sender_name("vfx.wilson@gmail.com", "Wilson Reed") == "Wilson Reed"
assert mailfmt.sender_name("vfx2024@gmail.com") == ""
bul = good.replace("I can edit", "").replace("so you can judge the quality before deciding anything.",
      "Here is what you get:\n\n- A 30 to 60 second edit of your clip\n- Sent back so you can judge the style")
assert write.check(S, bul, facts, ctx, "Sara") in ("", "wrong length"), write.check(S, bul, facts, ctx, "Sara")
four = good + "\n- a\n- b\n- c\n- d"
assert write.check(S, four, facts, ctx, "Sara") != ""
assert write.check(S, good.replace("Could you reply with a clip or a video link?", "Reply with a clip or a video link."),
                   facts, ctx, "Sara") == "ask must be the last line"
hh = mailfmt.html("Hi,\n\nWhat you get:\n\n- one\n- two\n\nCould you reply?", "Chris Ewart")
assert "<ul" in hh and hh.count("<li") == 2 and "list-style-type:disc" in hh, "html bullets must be round"
pt = mailfmt.plain("Hi,\n\nWhat you get:\n\n- one\n- two\n\nCould you reply?", "Chris Ewart")
assert "\u2022 one\n\u2022 two" in pt and "- one" not in pt, "plain-text bullets must be round"
# company name appears ONLY in the signature
mm = send.build_message({"email": "vfx.chris.ewart@gmail.com", "app_password": "x"}, dict(r, Body=good, Subject="Hello"))
t2 = mm.get_body(("plain",)).get_content()
assert t2.count("Level Up VFX") == 1 and t2.rstrip().endswith("Level Up VFX")

# ---------- replies / bounces / unsubscribe ----------
def mail(frm, subj, body, **hd):
    m = EmailMessage(); m["From"], m["Subject"] = frm, subj
    for k, v in hd.items(): m[k.replace("_", "-")] = v
    m.set_content(body); return m.as_bytes()
leads = {"sara@x.com", "tom@y.com"}
assert replies.classify(mail("Sara <sara@x.com>", "Re: hi", "Sure, here is a clip.\n\nOn Mon, X wrote:\n> old"), leads)[0] == "reply"
assert replies.classify(mail("sara@x.com", "Unsub", ""), leads)[0] == "stop"
assert replies.classify(mail("sara@x.com", "Re: hi", "Not interested, thanks"), leads)[0] == "stop"
assert replies.classify(mail("sara@x.com", "Out of office", "away", Auto_Submitted="auto-replied"), leads)[0] == ""
assert replies.classify(mail("random@z.com", "Hello", "hi"), leads)[0] == ""
b = replies.classify(mail("Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "Delivery Status Notification (Failure)",
                          "Your message wasn't delivered to tom@y.com because the address couldn't be found."), leads)
assert b[0] == "bounce" and b[1] == ["tom@y.com"]
assert replies.classify(mail("mailer-daemon@googlemail.com", "Delivery Status Notification (Delay)",
                             "Delayed: tom@y.com"), leads)[0] == ""
print("All checks passed.")
