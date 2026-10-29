"""Builds the closing + signature, and the plain-text and HTML versions of an email."""
import os, re
from html import escape
import settings as S


def sender_name(email, override=""):
    """vfx.chris.ewart@gmail.com -> 'Chris Ewart'. A "name" in GMAIL_ACCOUNTS always wins."""
    if override and override.strip():
        return override.strip()
    local = email.split("@")[0]
    words = [w for w in re.split(r"[._\-+0-9]+", local) if w and w.lower() not in S.NAME_IGNORE]
    return " ".join(w.capitalize() for w in words)


def sig_lines(name):
    lines = [name, S.SIGN_TITLE, S.SIGN_COMPANY]
    postal = (os.getenv("POSTAL_ADDRESS") or "").replace("\\n", ", ").strip()
    if postal:
        lines.append(postal)
    return [l for l in lines if l]


def plain(body, name):
    text = re.sub(r"(?m)^- ", "\u2022 ", body.strip())          # "- " lines become round bullets
    # blank line between "Best regards," and the signature
    return text + "\n\n" + S.CLOSING + "\n\n" + "\n".join(sig_lines(name))


def html(body, name):
    out, para, bullets = [], [], []

    def flush():
        if para:
            out.append('<p style="margin:0 0 14px 0">' + "<br>".join(escape(p) for p in para) + "</p>")
            para.clear()
        if bullets:
            out.append('<ul style="margin:0 0 14px 0;padding:0 0 0 22px;list-style-type:disc;list-style-position:outside">'
                       + "".join(f'<li style="margin:0 0 4px 0">{escape(b)}</li>' for b in bullets) + "</ul>")
            bullets.clear()

    for line in body.strip().splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("- "):
            if para:
                flush()
            bullets.append(s[2:].strip())
        else:
            if bullets:
                flush()
            para.append(s)
    flush()
    style = f"font-family:{S.SIGN_FONT};font-size:{S.SIGN_SIZE};color:{S.SIGN_COLOR};line-height:1.5;margin:0"
    # <br><br> = one empty line between "Best regards," and the signature
    sig = f'<p style="{style}">{escape(S.CLOSING)}<br><br>' + "<br>".join(escape(l) for l in sig_lines(name)) + "</p>"
    return "<div>" + "".join(out) + sig + "</div>"
