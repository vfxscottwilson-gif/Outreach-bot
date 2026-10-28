"""Collects public facts about a lead: YouTube (API, cheap calls only), their website, their link pages."""
import os, re, json, urllib.request, urllib.parse, urllib.error
from html.parser import HTMLParser

EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]")
BLOCKED = ("linkedin.com", "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com", "tiktok.com",
           "youtube.com", "youtu.be", "wa.me", "whatsapp.com", "t.me", "discord.gg", "snapchat.com", "pinterest.com")


def safe(s):
    """Removes characters our own spam check forbids, so a title like 'WOW!' cannot fail every draft."""
    s = re.sub(r"https?://\S+|www\.\S+", " ", str(s))
    s = EMOJI.sub("", s).replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"[!$%\[\]{}<>@#]", "", s)
    return re.sub(r"\s+", " ", s).strip()


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.skip, self.links = [], 0, []

    def handle_starttag(self, t, a):
        if t in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if t == "a":
            for k, v in a:
                if k == "href" and v:
                    self.links.append(v)

    def handle_endtag(self, t):
        if t in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip and d.strip():
            self.out.append(d.strip())


def allowed(url):
    p = urllib.parse.urlparse(url if "//" in url else "https://" + url)
    host = p.netloc.lower().removeprefix("www.")
    return p.scheme in ("http", "https") and bool(host) and "." in host and not any(
        host == d or host.endswith("." + d) for d in BLOCKED)


def fetch(url):
    """-> (text, links) or ("", []). Never raises."""
    if not url or not allowed(url):
        return "", []
    url = url if url.startswith("http") else "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; research)"})
        html = urllib.request.urlopen(req, timeout=15).read(300000).decode("utf-8", "ignore")
        p = _Text()
        p.feed(html)
        return safe(" ".join(p.out)), [urllib.parse.urljoin(url, h) for h in p.links]
    except Exception:
        return "", []


def tokens(s):
    return [t for t in re.split(r"[,\s;|]+", str(s).strip()) if "." in t and ("/" in t or t.startswith("http"))]


def website_facts(website):
    """-> (homepage text, about-page text). Two requests at most."""
    web = (re.split(r"[,\s;|]+", website.strip()) or [""])[0]
    text, links = fetch(web)
    about = ""
    if text:
        host = urllib.parse.urlparse(web if "//" in web else "https://" + web).netloc.lower().removeprefix("www.")
        for l in links:
            lh = urllib.parse.urlparse(l).netloc.lower().removeprefix("www.")
            if re.search(r"about|meet|story|who-we|me/?$", l.lower()) and (lh == host or not lh):
                about, _ = fetch(l)
                break
    return text[:1500], about[:900]


class YouTube:
    """Channel lookup + latest uploads. About 2 quota units per channel (the daily limit is 10,000).
    Never uses 'search' (100 units). Results are cached per channel for the run."""

    def __init__(self, key):
        self.key, self.cache, self.off = key, {}, not key

    def _get(self, path, **p):
        p["key"] = self.key
        url = "https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(p))
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)

    def _channel_params(self, url):
        h = re.search(r"youtube\.com/(@[^/?#\s]+)", url)
        c = re.search(r"youtube\.com/channel/(UC[\w\-]+)", url)
        u = re.search(r"youtube\.com/user/([^/?#\s]+)", url)
        cc = re.search(r"youtube\.com/c/([^/?#\s]+)", url)
        if c:
            return [{"id": c.group(1)}]
        if h:
            return [{"forHandle": urllib.parse.unquote(h.group(1))}]
        if u:
            return [{"forUsername": urllib.parse.unquote(u.group(1))}]
        if cc:
            n = urllib.parse.unquote(cc.group(1))
            return [{"forHandle": "@" + n}, {"forUsername": n}]
        v = re.search(r"(?:youtu\.be/|[?&]v=)([\w\-]{11})", url)
        if v:                                         # a video link: find its channel first (1 unit)
            d = self._get("videos", part="snippet", id=v.group(1))
            if d.get("items"):
                return [{"id": d["items"][0]["snippet"]["channelId"]}]
        return []

    def info(self, url):
        """-> dict(title, description, videos[]) or None. Raises nothing except after disabling itself."""
        if self.off or not url or "youtu" not in url:
            return None
        if url in self.cache:
            return self.cache[url]
        res = None
        try:
            for q in self._channel_params(url):
                d = self._get("channels", part="snippet,contentDetails", **q)
                if d.get("items"):
                    it = d["items"][0]
                    v = self._get("playlistItems", part="snippet", maxResults=5,
                                  playlistId=it["contentDetails"]["relatedPlaylists"]["uploads"])
                    res = {"title": safe(it["snippet"].get("title", "")),
                           "description": safe(it["snippet"].get("description", ""))[:500],
                           "videos": [safe(x["snippet"]["title"]) for x in v.get("items", [])
                                      if x["snippet"].get("title") and x["snippet"]["title"] not in ("Private video", "Deleted video")]}
                    break
        except urllib.error.HTTPError as e:
            print("YouTube lookup failed:", e.code)
            if e.code in (400, 403):                   # bad key or daily quota used up: carry on without YouTube
                self.off = True
        except Exception as e:
            print("YouTube lookup failed:", type(e).__name__)
        self.cache[url] = res
        return res


def build_context(lead, yt, web_cache=None):
    """Returns (context text for the AI, name_sources dict, facts_count, extra info dict).
    Only fields that are safe to quote. Scores, prices, tiers, subscribers and 'Found On' never go to the AI."""
    info = yt.info(lead["Url"]) if lead["Url"] else None
    web = (re.split(r"[,\s;|]+", lead["Website"].strip()) or [""])[0]
    site, about = ("", "")
    if web:
        web_cache = {} if web_cache is None else web_cache
        if web not in web_cache:
            web_cache[web] = website_facts(web)
        site, about = web_cache[web]
    extras = []
    for u in tokens(lead["Socials"])[:3]:
        t, _ = fetch(u)
        if t:
            extras.append(t[:600])
    channel = safe(lead["Channel"]) or (info["title"] if info else "")
    videos = ([safe(lead["Latest Video"])] if lead["Latest Video"] and lead["Latest Video"].lower() != "n/a" else []) \
        or (info["videos"][:3] if info else [])
    desc = info["description"] if info else ""
    pairs = [("Channel", channel), ("Niche", safe(lead["Niche"])), ("YouTube topics", safe(lead["Topics"])),
             ("Latest videos", " | ".join(videos)), ("Channel description", desc[:400]),
             ("Website", web if allowed(web) else ""), ("Website text", site), ("About page text", about)] \
        + [("Extra page", e) for e in extras] + [("Notes", safe(lead["Notes"]))]
    ctx = "\n".join(f"{k}: {v}" for k, v in pairs if v)
    facts = sum(1 for k, v in pairs if v and k not in ("Channel", "Niche", "Website"))
    name_src = {"Channel name": channel, "Channel description": desc, "Website text": site[:600],
                "About page text": about[:600], "Notes": safe(lead["Notes"]), "Name column": lead["Name"]}
    return ctx, name_src, facts, {"channel": channel, "has_site": bool(site), "has_yt": bool(info)}
