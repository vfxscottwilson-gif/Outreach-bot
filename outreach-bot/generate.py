"""Phase 1: read the master tab, research each new lead, write a personal email, add it to 'Ready to Send'.
Sends nothing. Needs no Gmail login. Safe to run again and again: finished leads are never repeated.
IMPORTANT: this file never prints email addresses or names. GitHub run logs can be public."""
import os, re, sys, time
import compose, names
from sheetio import Master, Output, Log, open_book, first_email, score
from research import YouTube, build_context
from verify import Verifier
import llm as llmmod

NO_WORDS = {"no", "false", "0", "n", "inactive", "dead", "stopped", "closed"}
STOP_STATUS = {"stop", "unsubscribed", "replied", "bounced", "invalid", "do not contact", "dnc", "blocked", "sent"}
MAX_FAILS = 3
FLUSH_EVERY = 10


def env(name, default=""):
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


def yes(name, default):
    return env(name, default).lower() in ("yes", "true", "1", "y")


def run(master_ws, out_ws, log_ws, llm, yt, verifier, limit, deadline, optout=True, allow_risky=False,
        pause=0.0, dry=False, web_cache=None):
    master, out, log = Master(master_ws), Output(out_ws), Log(log_ws)
    out.ensure_header()
    have, bodies, _ = out.read()
    done = have | log.written                                  # also remembers rows you deleted after sending
    recent = {" ".join(compose.norm(b).split()[:5]) for b in bodies}
    leads = sorted(master.rows, key=lambda r: -score(r))        # best Score first (stable for ties)
    stats = {"written": 0, "skipped": 0, "failed": 0, "low_data": 0, "stopped_early": ""}
    pending, processed, seen = [], 0, set()

    def flush():
        if not pending:
            return
        if dry:
            stats["written"] += len(pending)
            pending.clear()
            return
        rows = [p["row"] for p in pending]
        n = out.append(rows)                                    # one write call for the whole batch
        for p in pending:
            log.add(p["row"][0], "written", p["detail"])
        log.flush()
        stats["written"] += n
        pending.clear()

    try:
        for lead in leads:
            if time.time() > deadline:
                stats["stopped_early"] = "time limit"
                break
            raw = lead["Email"].strip()
            email = first_email(raw)
            if not raw:
                continue                                        # empty row
            key = email or raw.lower()[:80]
            if email and email in seen:
                log.add(email, "skipped - duplicate in master", f"row {lead['_row']}")
                stats["skipped"] += 1
                continue
            seen.add(email or key)
            if email in done:
                continue
            if not email:
                log.add(key, "skipped - invalid email", f"row {lead['_row']}: no email address found")
                stats["skipped"] += 1
                continue
            if lead["Active"].strip().lower() in NO_WORDS:
                log.add(email, "skipped - inactive", f"row {lead['_row']}")
                stats["skipped"] += 1
                continue
            if lead["Status"].strip().lower() in STOP_STATUS:
                log.add(email, "skipped - status in master", f"row {lead['_row']}: {lead['Status']}")
                stats["skipped"] += 1
                continue
            if log.has(email, "skipped - invalid email") or (log.has(email, "skipped - risky email") and not allow_risky):
                continue                                        # already checked and logged: do not spend credits again
            if log.fails.get(email, 0) >= MAX_FAILS:
                log.add(email, "gave up", f"row {lead['_row']}: failed {MAX_FAILS} times")
                stats["skipped"] += 1
                continue
            if processed >= limit:
                stats["stopped_early"] = "run limit"
                break
            processed += 1
            try:
                res, why = verifier.check(email)
                if res == "invalid":
                    log.add(email, "skipped - invalid email", f"row {lead['_row']}: {why}")
                    stats["skipped"] += 1
                    continue
                if res == "risky" and not allow_risky:
                    log.add(email, "skipped - risky email", f"row {lead['_row']}: {why}")
                    stats["skipped"] += 1
                    continue
                ctx, name_src, facts_n, info = build_context(lead, yt, web_cache)
                angle = compose.pick_angle(lead["Angle"])
                r = compose.write_one(llm, lead, ctx, name_src, facts_n, info["channel"], angle, processed, recent, optout)
                if not r["ok"]:
                    log.add(email, "failed", f"row {lead['_row']}: {r['error']}", repeat=True)
                    stats["failed"] += 1
                    continue
                row = [email, r["name"], r["subject"], r["body"]]
                bad = compose.validate_final(row)
                if bad:
                    log.add(email, "failed", f"row {lead['_row']}: {bad}", repeat=True)
                    stats["failed"] += 1
                    continue
                recent.add(" ".join(compose.norm(r["body"]).split()[:5]))
                detail = f"row {lead['_row']}; angle {angle}; name {'found' if r['name'] != names.TEAM else 'Team'}"
                if r["low_data"]:
                    detail += "; low data"
                    stats["low_data"] += 1
                pending.append({"row": row, "detail": detail})
                if len(pending) >= FLUSH_EVERY:
                    flush()
                if pause:
                    time.sleep(pause)
            except llmmod.Exhausted:
                stats["stopped_early"] = "AI quota used up (finished rows are saved; run again later)"
                break
            except Exception as e:                              # one bad lead must never stop the run
                log.add(email, "failed", f"row {lead['_row']}: {type(e).__name__}", repeat=True)
                stats["failed"] += 1
    finally:
        flush()
        if not dry:
            log.flush()
    return stats


def main():
    limit = int(env("RUN_LIMIT", "25"))
    deadline = time.time() + 60 * int(env("MAX_RUN_MIN", "40"))
    llm = llmmod.from_env()                                     # fail early if no AI key
    master_ws, out_ws, log_ws = open_book()
    yt = YouTube(env("YOUTUBE_KEY"))
    verifier = Verifier(env("ZEROBOUNCE_KEY"), limit, yes("ALLOW_ROLE", "yes"), yes("VERIFY_MX", "yes"))
    st = run(master_ws, out_ws, log_ws, llm, yt, verifier, limit, deadline,
             optout=yes("INCLUDE_OPTOUT", "yes"), allow_risky=yes("ALLOW_RISKY", "no"),
             pause=float(env("WRITE_PAUSE", "4")), dry=yes("DRY_RUN", "no"))
    print("DONE. written %(written)d, skipped %(skipped)d, failed %(failed)d, low-data %(low_data)d" % st
          + (f". Stopped early: {st['stopped_early']}" if st["stopped_early"] else ""))


if __name__ == "__main__":
    main()
