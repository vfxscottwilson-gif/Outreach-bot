"""Step 1: skip dead leads, check every new email address, pull YouTube channel details."""
import os, re, json, urllib.request, urllib.parse, urllib.error
from common import Sheet, first_email, norm_status, NO_WORDS, YES_WORDS

BAD_LOCAL = {"noreply", "no-reply", "donotreply", "do-not-reply", "webmaster", "postmaster", "abuse",
             "mailer-daemon", "root"}
BAD_DOMAIN = {"example.com", "test.com", "domain.com", "email.com", "youremail.com", "sentry.io"}
ROLE_SOFT = {"info", "admin", "support", "sales", "contact", "hello", "office", "team", "help", "mail"}
STATE = {"zb": os.getenv("ZEROBOUNCE_KEY") or None, "budget": int(os.getenv("VERIFY_API_PER_RUN") or 5),
         "yt": os.getenv("YOUTUBE_KEY") or None, "mx": {},
         "allow_role": (os.getenv("ALLOW_ROLE") or "yes").lower() != "no"}


def get(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def has_mx(domain):
    if domain not in STATE["mx"]:
        try:
            d = get("https://dns.google/resolve?name=%s&type=MX" % urllib.parse.quote(domain))
            st = d.get("Status")
            if st == 3:
                STATE["mx"][domain] = False                      # domain does not exist
            elif st == 0:
                STATE["mx"][domain] = any(
                    a.get("type") == 15 and not str(a.get("data", "")).strip().endswith(" .")
                    for a in d.get("Answer", []))                # "0 ." is a null MX = no mail
            else:
                STATE["mx"][domain] = None                       # DNS hiccup: try again next run
        except Exception:
            STATE["mx"][domain] = None
    return STATE["mx"][domain]


def verify(raw):
    email = first_email(raw)
    if not email:
        return "Invalid", "syntax"
    local, _, domain = email.partition("@")
    if local in BAD_LOCAL or domain in BAD_DOMAIN or (local in ROLE_SOFT and not STATE["allow_role"]):
        return "Invalid", "role"
    mx = has_mx(domain)
    if mx is None:
        return None, ""
    if not mx:
        return "Invalid", "no-mx"
    if STATE["zb"] and STATE["budget"] > 0:
        try:
            d = get("https://api.zerobounce.net/v2/validate?api_key=%s&email=%s&ip_address="
                    % (STATE["zb"], urllib.parse.quote(email)))
            if d.get("error"):
                STATE["zb"] = None
            else:
                STATE["budget"] -= 1
                st = d.get("status")
                if st == "valid":
                    return "Valid", "api"
                if st in ("catch-all", "unknown"):
                    return "Risky", "api"
                if st:
                    return "Invalid", "api"
        except Exception:
            STATE["zb"] = None   # out of credits or error: free checks only
    return "Valid", "mx"


def yt(path, **p):
    p["key"] = STATE["yt"]
    return get("https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(p)))


def enrich(url):
    h = re.search(r"youtube\.com/(@[\w.\-%]+)", url)
    c = re.search(r"youtube\.com/channel/(UC[\w\-]+)", url)
    u = re.search(r"youtube\.com/user/([\w.\-]+)", url)
    q = ({"forHandle": urllib.parse.unquote(h.group(1))} if h else {"id": c.group(1)} if c
         else {"forUsername": u.group(1)} if u else None)
    if not q:
        return None
    d = yt("channels", part="snippet,contentDetails", **q)
    if not d.get("items"):
        return None
    it = d["items"][0]
    v = yt("playlistItems", part="snippet", maxResults=1,
           playlistId=it["contentDetails"]["relatedPlaylists"]["uploads"])
    title = v["items"][0]["snippet"]["title"] if v.get("items") else ""
    return it["snippet"]["title"], title


def main():
    limit = int(os.getenv("PREP_LIMIT") or 100)
    skip_credit = (os.getenv("SKIP_EDITOR_CREDIT") or "no").lower() == "yes"
    sh = Sheet()
    seen, v, e, since = set(), 0, 0, 0
    for i, r in enumerate(sh.rows):
        n, email = i + 2, first_email(r["Email"])
        dup = email in seen
        if email:
            seen.add(email)
        if email and norm_status(r["Status"]) in ("", "new") and v < limit:
            active, credit = r["Active"].strip().lower(), r["Has Editor Credit"].strip().lower()
            if active in NO_WORDS:
                status, how = "Skipped", "inactive"
            elif skip_credit and credit in YES_WORDS:
                status, how = "Skipped", "has editor"
            elif dup:
                status, how = "Duplicate", ""
            else:
                status, how = verify(r["Email"])
            if status:
                v += 1
                since += 1
                sh.put(n, Status=status, Verified=how)
        if (STATE["yt"] and r["Url"] and not r["Latest Video"] and e < limit
                and norm_status(r["Status"]) not in ("stop", "invalid", "duplicate", "skipped")):
            try:
                res = enrich(r["Url"])
                e += 1
                since += 1
                if res:
                    sh.put(n, Latest_Video=res[1] or "n/a")
                    if not r["Channel"]:
                        sh.put(n, Channel=res[0])
                else:
                    sh.put(n, Latest_Video="n/a")      # not a channel link we can read: do not retry forever
            except urllib.error.HTTPError as ex:
                print("YouTube lookup failed:", ex.code)
                if ex.code in (400, 403):              # bad key or daily quota used up
                    STATE["yt"] = None
            except Exception as ex:
                print("YouTube lookup failed:", type(ex).__name__)
        if since >= 25:
            sh.flush()
            since = 0
    sh.flush()
    print(f"verified {v}, enriched {e}")


if __name__ == "__main__":
    main()
