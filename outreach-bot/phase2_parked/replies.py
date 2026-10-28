"""Step 4: read replies and bounces in your Gmail inboxes and update the sheet.
Unsub / not interested  -> Status Stop.   Any other human reply -> Status Replied.   Bounce -> Status Bounced.
Messages stay unread: the robot only looks."""
import os, re, json, imaplib, email
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr
from common import Sheet, EMAIL_FIND, first_email, norm_status

STOP_RE = re.compile(r"\b(unsub\w*|stop|remove|opt[- ]?out|not interested|no thanks|no thank you|"
                     r"do not (email|contact)|don'?t (email|contact)|take me off|leave me alone)\b", re.I)
BOUNCE_SUBJ = re.compile(r"undeliver|delivery status notification \(failure\)|mail delivery (failed|subsystem)|"
                         r"returned mail|failure notice|delivery failure|couldn'?t be delivered", re.I)
RANK = {"sent": 1, "replied": 2, "stop": 3}


def decode(v):
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return str(v or "")


def text_of(msg):
    parts = []
    for p in msg.walk():
        if p.get_content_type() in ("text/plain", "message/delivery-status") and not p.is_multipart():
            try:
                payload = p.get_payload(decode=True) or b""
                parts.append(payload.decode(p.get_content_charset() or "utf-8", "ignore"))
            except Exception:
                pass
        elif p.get_content_type() == "message/delivery-status":
            parts.append(str(p))
    return "\n".join(parts)


def reply_text(body):
    out = []
    for ln in body.splitlines():
        if re.match(r"^\s*(on .{5,80} wrote:|-{2,}\s*original message|from:\s)", ln, re.I):
            break
        if not ln.lstrip().startswith(">"):
            out.append(ln)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def classify(raw, lead_emails):
    """Returns (kind, [matching lead emails], snippet) where kind is 'bounce', 'stop', 'reply' or ''."""
    msg = email.message_from_bytes(raw)
    sender = parseaddr(msg.get("From", ""))[1].lower()
    subject = decode(msg.get("Subject"))
    body = text_of(msg)
    auto = (msg.get("Auto-Submitted", "") or "").lower() not in ("", "no") \
        or "auto" in (msg.get("Precedence", "") or "").lower() or (msg.get("X-Autoreply") is not None)
    if sender.startswith(("mailer-daemon@", "postmaster@")) or BOUNCE_SUBJ.search(subject):
        if re.search(r"delay", subject, re.I) and not re.search(r"action:\s*failed", body, re.I):
            return "", [], ""
        found = [e.lower() for e in EMAIL_FIND.findall(body)]
        hits = sorted({e for e in found if e in lead_emails})
        return ("bounce", hits, "bounce") if hits else ("", [], "")
    if sender in lead_emails:
        if auto:
            return "", [], ""
        text = reply_text(body)
        kind = "stop" if STOP_RE.search(subject + " " + text) else "reply"
        return kind, [sender], (subject + " | " + text)[:200]
    return "", [], ""


def scan(acct, days, lead_emails):
    found = []
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%d-%b-%Y")
    with imaplib.IMAP4_SSL("imap.gmail.com", 993) as m:
        m.login(acct["email"], acct["app_password"])
        for folder in ("INBOX", "[Gmail]/Spam"):
            try:
                if m.select(folder, readonly=True)[0] != "OK":
                    continue
                typ, data = m.search(None, "SINCE", since)
                for num in (data[0].split() if typ == "OK" and data and data[0] else []):
                    typ, msgdata = m.fetch(num, "(BODY.PEEK[])")
                    if typ == "OK" and msgdata and isinstance(msgdata[0], tuple):
                        found.append(classify(msgdata[0][1], lead_emails))
            except imaplib.IMAP4.error:
                continue
    return found


def main():
    days = int(os.getenv("REPLY_DAYS") or 3)
    try:
        accounts = json.loads(os.environ["GMAIL_ACCOUNTS"])
    except Exception:
        raise SystemExit("GMAIL_ACCOUNTS secret is missing or invalid.")
    sh = Sheet()
    by_email = {}
    for i, r in enumerate(sh.rows):
        em = first_email(r["Email"])
        if em and norm_status(r["Status"]) in RANK:
            by_email.setdefault(em, i + 2)
    changed = 0
    for a in accounts:
        try:
            results = scan(a, days, set(by_email))
        except Exception as e:
            print("inbox check failed for one account:", type(e).__name__)
            continue
        for kind, emails, snippet in results:
            for em in emails:
                n = by_email[em]
                cur = norm_status(sh.rows[n - 2]["Status"])
                if kind == "bounce" and cur == "sent":
                    sh.put(n, Status="Bounced", Reply="bounce")
                elif kind in ("stop", "reply"):
                    new = "stop" if kind == "stop" else "replied"
                    if RANK.get(new, 0) > RANK.get(cur, 0):
                        sh.put(n, Status="Stop" if new == "stop" else "Replied", Reply=snippet)
                    else:
                        continue
                else:
                    continue
                changed += 1
    sh.flush()
    print("updated", changed)


if __name__ == "__main__":
    main()
