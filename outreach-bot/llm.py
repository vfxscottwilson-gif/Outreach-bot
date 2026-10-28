"""Talks to the AI providers you configured, in this order: Gemini, Anthropic, OpenAI.
 - Several keys per provider are fine: GEMINI_KEY = key1,key2,key3 (rotates when one is rate limited).
 - A provider is used only if its key (and, for Anthropic/OpenAI, its *_MODEL variable) is set.
 - Rate limits: waits and retries. A key that keeps failing is switched off for the run.
 - If every provider is out of quota, Exhausted is raised and the run stops cleanly (finished rows are saved)."""
import os, re, json, time, urllib.request, urllib.error


class Exhausted(Exception):
    pass


class Transient(Exception):
    pass


def _post(url, headers, payload):
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", str(text).strip(), flags=re.M).strip()
    try:
        out = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise Transient("no JSON in reply")
        try:
            out = json.loads(m.group(0))
        except ValueError:
            raise Transient("bad JSON in reply")
    if not isinstance(out, dict):
        raise Transient("JSON is not an object")
    return out


class Provider:
    def __init__(self, name, keys, model, build):
        self.name, self.model, self.build = name, model, build
        self.st = [{"key": k, "fails": 0, "cool": 0.0, "dead": False} for k in keys]

    def alive(self):
        return any(not s["dead"] for s in self.st)

    def call(self, system, user):
        for _ in range(8):
            live = [s for s in self.st if not s["dead"]]
            if not live:
                raise Exhausted(self.name)
            s = min(live, key=lambda x: x["cool"])
            wait = s["cool"] - time.time()
            if wait > 0:
                time.sleep(min(wait, 65))
            for attempt in range(3):
                try:
                    text = self.build(s["key"], self.model, system, user)
                    s["fails"] = 0
                    return parse_json(text)
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        s["fails"] += 1
                        s["cool"] = time.time() + 60
                        if s["fails"] >= 3:              # three limits in a row with no success: out of quota
                            s["dead"] = True
                            print(f"{self.name}: a key is out of quota, switching it off for this run")
                        break                            # pick the next key (or wait for this one)
                    if e.code in (400, 401, 403, 404):
                        s["dead"] = True
                        print(f"{self.name}: key or model rejected (HTTP {e.code}). Check the key and the model name.")
                        break
                    if attempt < 2:
                        time.sleep((5, 15)[attempt])
                        continue
                    raise Transient(f"{self.name} HTTP {e.code}")
                except (urllib.error.URLError, TimeoutError, OSError):
                    if attempt < 2:
                        time.sleep((5, 15)[attempt])
                        continue
                    raise Transient(f"{self.name} network error")
        raise Exhausted(self.name)


def _gemini(key, model, system, user):
    d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
              {"x-goog-api-key": key},
              {"systemInstruction": {"parts": [{"text": system}]},
               "contents": [{"role": "user", "parts": [{"text": user}]}],
               "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}})
    try:
        return d["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise Transient("Gemini returned no text (blocked or empty)")


def _anthropic(key, model, system, user):
    d = _post("https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"},
              {"model": model, "max_tokens": 1200, "temperature": 0.7, "system": system,
               "messages": [{"role": "user", "content": user}]})
    try:
        return "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
    except (KeyError, TypeError):
        raise Transient("Anthropic returned no text")


def _openai(key, model, system, user):
    d = _post("https://api.openai.com/v1/chat/completions", {"Authorization": "Bearer " + key},
              {"model": model, "temperature": 0.7, "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    try:
        return d["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise Transient("OpenAI returned no text")


def _keys(var):
    return [k.strip() for k in (os.getenv(var) or "").split(",") if k.strip()]


def from_env():
    provs = []
    for name, keyvar, modelvar, default, build in (
            ("Gemini", "GEMINI_KEY", "GEMINI_MODEL", "gemini-2.5-flash", _gemini),
            ("Anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "", _anthropic),
            ("OpenAI", "OPENAI_API_KEY", "OPENAI_MODEL", "", _openai)):
        keys, model = _keys(keyvar), (os.getenv(modelvar) or default).strip()
        if keys and not model:
            print(f"{name}: key found but {modelvar} variable is empty, so {name} is not used.")
        elif keys:
            provs.append(Provider(name, keys, model, build))
    if not provs:
        raise SystemExit("No AI key found. Add the GEMINI_KEY secret (and its GEMINI_MODEL variable).")
    print("AI providers:", ", ".join(p.name for p in provs))
    return LLM(provs)


class LLM:
    def __init__(self, providers):
        self.providers = providers

    def ask(self, system, user):
        for p in self.providers:
            if not p.alive():
                continue
            try:
                return p.call(system, user)
            except Exhausted:
                continue
        raise Exhausted("all providers")
