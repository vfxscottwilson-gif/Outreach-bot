"""Step 3: send approved emails from your Gmail accounts, in the US sending window."""
import os, json, math, random, smtplib, ssl, threading, time
from datetime import datetime, date
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from zoneinfo import ZoneInfo
import mailfmt
import settings
from common import Sheet, OPTOUT_LINE, first_email, norm_status, score

SUPPRESS = {"sent", "queued", "stop", "replied", "bounced"}


def daily_cap(today, start_date, start, step, target):
    if not start_date:
        return start
    try:
        days = max(0, (today - date.fromisoformat(start_date.strip())).days)
    except ValueError:
        print("CAP_START_DATE must look like 2026-10-27. Using the starting cap.")
        return start
    return min(target, start + step * days)


def build_message(acct, r):
    name = mailfmt.sender_name(acct["email"], acct.get("name", ""))
    msg = EmailMessage()
    msg["From"] = formataddr((name, acct["email"])) if name else acct["email"]
    msg["To"] = first_email(r["Email"])
    msg["Subject"] = r["Subject"].strip()
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=acct["email"].split("@")[-1])
    msg["List-Unsubscribe"] = f"<mailto:{acct['email']}?subject=Unsub>"
    body = r["Body"].replace("\x00", "").strip()
    if 'Reply "Unsub"' not in body:
        body += "\n\n" + OPTOUT_LINE
    msg.set_content(mailfmt.plain(body, name))
    if settings.SEND_HTML:
        msg.add_alternative(mailfmt.html(body, name), subtype="html")
    return msg


def main():
    tz = ZoneInfo(os.getenv("SEND_TZ") or "America/New_York")
    h0, h1 = int(os.getenv("SEND_START") or 10), int(os.getenv("SEND_END") or 16)
    now = datetime.now(tz)
    ignore = os.getenv("IGNORE_HOURS") == "yes"
    if not ignore and not (now.weekday() < 5 and h0 <= now.hour < h1):
        print("Outside sending window")
        return
    cap = daily_cap(now.date(), os.getenv("CAP_START_DATE") or "", int(os.getenv("CAP_START") or 15),
                    int(os.getenv("CAP_STEP") or 2), int(os.getenv("CAP_TARGET") or 55))
    per_run = int(os.getenv("PER_RUN_MAX") or 15)
    dry = (os.getenv("DRY_RUN") or "no").lower() == "yes"
    dmin, dmax = int(os.getenv("DELAY_MIN") or 45), int(os.getenv("DELAY_MAX") or 120)
    deadline = time.time() + 60 * int(os.getenv("MAX_RUN_MIN") or 45)
    try:
        accounts = json.loads(os.environ["GMAIL_ACCOUNTS"])
        assert accounts and all("email" in a and "app_password" in a for a in accounts)
    except Exception:
        raise SystemExit('GMAIL_ACCOUNTS must look like [{"email":"a@gmail.com","app_password":"abcdabcdabcdabcd"}]')
    for a in accounts:
        if not mailfmt.sender_name(a["email"], a.get("name", "")):
            print("WARNING: cannot get a name from one Gmail address. Add \"name\" for it in GMAIL_ACCOUNTS.")

    sh = Sheet()
    lock = threading.Lock()
    today = now.strftime("%Y-%m-%d")
    sent = {a["email"]: 0 for a in accounts}
    for r in sh.rows:
        if r["Sender"] in sent and r["Sent At"].startswith(today):
            sent[r["Sender"]] += 1
    stuck = sum(1 for r in sh.rows if norm_status(r["Status"]) == "queued")
    if stuck:
        print(f"{stuck} row(s) are stuck on Queued. Check the Sent folder of the Sender account, then set them to Sent or Approved.")

    # Never email the same address twice, never email anyone who said stop or replied.
    taken = {}
    for i, r in enumerate(sh.rows):
        if norm_status(r["Status"]) in SUPPRESS:
            taken.setdefault(first_email(r["Email"]), i + 2)
    ready = []
    for i, r in enumerate(sh.rows):
        n = i + 2
        if norm_status(r["Status"]) != "approved":
            continue
        em = first_email(r["Email"])
        if not em:
            sh.put(n, Status="Review", Facts="bad email")
        elif not r["Subject"].strip() or not r["Body"].strip():
            sh.put(n, Status="Review", Facts="empty subject or body")
        elif em in taken:
            sh.put(n, Status="Duplicate", Facts="already emailed or stopped")
        else:
            taken[em] = n
            ready.append((n, r))
    sh.flush()
    ready.sort(key=lambda t: -score(t[1]))
    skipped_rows = set()

    remaining_hours = 1 if ignore else max(1, h1 - now.hour)
    jobs = {}
    for a in accounts:
        left = max(0, cap - sent[a["email"]])
        k = min(math.ceil(left / remaining_hours), left, per_run, len(ready))
        jobs[a["email"]] = [ready.pop(0) for _ in range(k)]
    total = sum(len(v) for v in jobs.values())
    print(f"cap/account today: {cap}; sending now: {total}; accounts: {len(accounts)}")
    if dry or not total:
        return
    for a in accounts:
        for row, _ in jobs[a["email"]]:
            sh.put(row, Status="Queued", Sender=a["email"])
    skipped_rows = sh.flush()
    for e in jobs:
        jobs[e] = [(row, r) for row, r in jobs[e] if row not in skipped_rows]

    def put_now(row, **cols):
        try:
            with lock:
                sh.put(row, **cols)
                sh.flush()
        except Exception as ex:
            print(f"sheet write failed for a row: {type(ex).__name__}")

    def work(idx, acct, items):
        done, fails = set(), 0
        try:
            time.sleep(random.randint(0, 120))          # stagger logins
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
                s.login(acct["email"], acct["app_password"])
                for row, r in items:
                    if time.time() > deadline:
                        print(f"account #{idx + 1}: time limit reached, the rest goes next run")
                        break
                    status, note = "Sent", ""
                    try:
                        s.send_message(build_message(acct, r))
                    except smtplib.SMTPRecipientsRefused:
                        status = "Bounced"
                    except (smtplib.SMTPServerDisconnected, smtplib.SMTPSenderRefused, smtplib.SMTPConnectError,
                            smtplib.SMTPAuthenticationError):
                        raise                                 # account problem: stop this account
                    except smtplib.SMTPResponseException as e:
                        text = str(getattr(e, "smtp_error", b"")).lower()
                        if e.smtp_code in (421, 450, 451, 452) or "limit" in text or "quota" in text:
                            raise                             # Gmail says slow down: stop this account
                        status, note = "Error", f"smtp {e.smtp_code}"
                    except Exception as e:
                        status, note = "Error", type(e).__name__
                    done.add(row)                             # from here on, never reset or resend this row
                    if status == "Error":
                        fails += 1
                        put_now(row, Status="Error", Facts=note, Sender="")
                        if fails >= 2:
                            print(f"account #{idx + 1} stopped: 2 failures in a row")
                            break
                        continue
                    fails = 0
                    put_now(row, Status=status, Sender=acct["email"],
                            Sent_At=datetime.now(tz).strftime("%Y-%m-%d %H:%M"),
                            Sending_Date=datetime.now(tz).strftime("%Y-%m-%d"))
                    time.sleep(random.randint(dmin, dmax))
        except Exception as e:
            print(f"account #{idx + 1} stopped:", type(e).__name__, getattr(e, "smtp_code", ""))
        finally:
            for row, _ in items:
                if row not in done:
                    put_now(row, Status="Approved", Sender="")

    ts = [threading.Thread(target=work, args=(i, a, jobs[a["email"]])) for i, a in enumerate(accounts) if jobs[a["email"]]]
    for t in ts:
        t.start()
    for t in ts:
        t.join()


if __name__ == "__main__":
    main()
