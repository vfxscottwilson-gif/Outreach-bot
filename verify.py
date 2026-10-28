"""Email checks before anything is written. Cheap and free first; ZeroBounce only if you added its key."""
import json, urllib.request, urllib.parse, re
from sheetio import first_email

BAD_LOCAL = {"noreply", "no-reply", "donotreply", "do-not-reply", "webmaster", "postmaster", "abuse",
             "mailer-daemon", "root", "unsubscribe", "bounce", "bounces"}
BAD_DOMAIN = {"example.com", "test.com", "domain.com", "email.com", "youremail.com", "sentry.io", "mail.com.invalid"}
ROLE_SOFT = {"info", "admin", "support", "sales", "contact", "hello", "office", "team", "help", "mail"}


def _get(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


class Verifier:
    def __init__(self, zb_key="", zb_budget=30, allow_role=True, check_mx=True):
        self.zb, self.budget, self.allow_role, self.check_mx = zb_key or None, zb_budget, allow_role, check_mx
        self.mx = {}

    def has_mx(self, domain):
        if domain not in self.mx:
            try:
                d = _get("https://dns.google/resolve?name=%s&type=MX" % urllib.parse.quote(domain))
                st = d.get("Status")
                if st == 3:
                    self.mx[domain] = False                       # domain does not exist
                elif st == 0:
                    self.mx[domain] = any(a.get("type") == 15 and not str(a.get("data", "")).strip().endswith(" .")
                                          for a in d.get("Answer", []))
                else:
                    self.mx[domain] = None                        # DNS hiccup: do not judge
            except Exception:
                self.mx[domain] = None
        return self.mx[domain]

    def check(self, raw):
        """-> ('ok' | 'invalid' | 'risky', reason)"""
        email = first_email(raw)
        if not email:
            return "invalid", "syntax"
        local, _, domain = email.partition("@")
        if local in BAD_LOCAL or domain in BAD_DOMAIN or (local in ROLE_SOFT and not self.allow_role):
            return "invalid", "role or fake address"
        if not re.fullmatch(r"[a-z0-9.\-]+\.[a-z]{2,}", domain):
            return "invalid", "bad domain"
        if self.check_mx and self.has_mx(domain) is False:
            return "invalid", "domain cannot receive email"
        if self.zb and self.budget > 0:
            try:
                d = _get("https://api.zerobounce.net/v2/validate?api_key=%s&email=%s&ip_address="
                         % (self.zb, urllib.parse.quote(email)))
                if d.get("error"):
                    self.zb = None
                else:
                    self.budget -= 1
                    st = d.get("status")
                    if st == "valid":
                        return "ok", "verified"
                    if st in ("catch-all", "unknown"):
                        return "risky", st
                    if st:
                        return "invalid", st
            except Exception:
                self.zb = None                                    # out of credits or error: free checks only
        return "ok", "mx"
