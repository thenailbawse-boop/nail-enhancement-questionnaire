"""Write down every word of a video, with times. Copied from ~/vibe-editing/replay_shorts/transcribe_all.py
(2026-10-26) so the dashboard works on any Mac with the Vibe Editing kit.
Groq's free key first (from the kit's keys.env). If there is no key, or Groq asks to wait a long time,
that 20 minute piece is done on this computer instead."""
import json, os, re, time
import requests

HOME = os.path.expanduser("~")
KEYS = os.path.join(HOME, "vibe-editing/plugins/vibe-editing/config/keys.env")
PROMPT = "Claude, Claude Code, ChatGPT, Skool, Wispr Flow, GoHighLevel, n8n, Higgsfield, ManyChat."
CHUNK = 1200
_local = None
log = print


def groq_key():
    try:
        m = re.search(r"^GROQ_API_KEY=(\S+)", open(KEYS).read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def local_model():
    global _local
    if _local is None:
        from faster_whisper import WhisperModel
        _local = WhisperModel("small.en", device="cpu", compute_type="int8")
    return _local


def groq(path, prompt=PROMPT):
    """Return (words, segments) or None if there is no key or Groq wants a long wait.
    2026-10-30: with the word hint, Groq's large model began answering with the hint itself ("N8n, Higgsfield,
    ManyChat.") or "Thank you for watching." for 18 s of clear talking. Under 1 word per 4 seconds of sound is
    not a transcript, so it asks once more without the hint."""
    key = groq_key()
    if not key:
        return None
    for attempt in range(6):
        try:
            r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                              headers={"Authorization": f"Bearer {key}"},
                              files={"file": (os.path.basename(path), open(path, "rb"), "audio/mpeg")},
                              data={"model": "whisper-large-v3", "response_format": "verbose_json",
                                    "timestamp_granularities[]": ["word", "segment"], "language": "en",
                                    **({"prompt": prompt} if prompt else {})}, timeout=(30, 240))
        except Exception as e:
            log(f"   network error {type(e).__name__}")
            if attempt >= 1:
                return None
            time.sleep(30); continue
        if r.status_code == 200:
            d = r.json()
            if prompt and len(d.get("words", [])) < float(d.get("duration") or 0) / 4:
                log("   the transcript came back nearly empty, asking again without the word hint")
                return groq(path, prompt="")
            return fix_names(d.get("words", [])), d.get("segments", [])
        if r.status_code == 429:
            try:
                wait = float(r.headers.get("retry-after") or 60)
            except ValueError:
                wait = 60
            if wait > 120:
                log("   the free plan's hourly limit is used up, this computer takes over")
                return None
            time.sleep(wait + 2); continue
        log(f"   Groq said {r.status_code}")
        time.sleep(20)
    return None


def local(path):
    segs, _ = local_model().transcribe(path, language="en", word_timestamps=True, initial_prompt=PROMPT, vad_filter=False)
    words, out = [], []
    for s in segs:
        out.append({"start": s.start, "end": s.end, "text": s.text})
        for w in (s.words or []):
            words.append({"word": w.word, "start": w.start, "end": w.end})
    return fix_names(words), out


# the speech reader writes "Claude" as "cloud", "your cloud core subscription" on Tiff's own video (2026-11-03). Real cloud
# talk has to stay: this ships to everyone, and the old one-word swap also turned every real "school" into "Skool".
NAME_NEXT = {"code", "core", "coat", "cowork", "opus", "sonnet", "haiku"}
NAME_NEXT_AI = {"desktop", "skill", "skills", "plugin", "plugins", "connector", "connectors", "artifact", "artifacts", "subscription", "max"}
NAME_BEFORE = {"with", "in", "inside", "into", "ask", "asked", "asking", "use", "used", "using", "open", "opened", "tell", "told", "hey", "called", "versus", "vs"}
REAL_BEFORE = {"the", "a", "an", "this", "that", "google", "amazon", "aws", "microsoft", "azure", "oracle", "apple", "sound", "dark", "rain", "storm",
               "white", "black", "big", "gray", "grey", "tag", "word", "mushroom", "private", "public", "hybrid", "dust"}
REAL_AFTER = {"storage", "based", "computing", "server", "servers", "hosting", "drive", "backup", "backups", "service", "services", "account", "accounts",
              "sync", "flare", "run", "function", "functions", "platform", "platforms", "software", "provider", "providers", "nine", "of", "cover", "native",
              "security", "kitchen", "data", "phone", "file", "files", "folder", "folders"}
AI_TALK = {"ai", "chatgpt", "gpt", "gemini", "grok", "anthropic", "claude", "prompt", "prompts", "chatbot", "automation", "automations", "agent", "agents", "n8n", "llm"}
SKOOL_NEXT = {"community", "communities", "classroom", "group", "groups", "post", "posts", "calendar", "leaderboard"}


def _bare(word):
    return re.sub(r"[^\w']", "", word.replace("’", "'")).lower()


def _swap(w, name):
    w["word"] = re.sub(r"(?i)cloud|clawed|clawd|claude|claud|school|whisper", name, w["word"], count=1)


def fix_names(words):
    """Change the name in each word it hears wrong, in place, and keep every time as it was. Safe to run twice."""
    # spellings of a tool that are never a real word, in every caption path (2026-11-04: CHADGBT and CLOUDFARE on Tiff's video)
    for i, w in enumerate(words):
        w["word"] = re.sub(r"(?i)chadgbt|chatgbt|chhatgpt|chadgpt|chadgpd", "ChatGPT", w["word"])
        w["word"] = re.sub(r"(?i)cloudfare", "Cloudflare", w["word"])
        if _bare(w["word"]) in {"chat", "chad"} and i + 1 < len(words) and _bare(words[i + 1]["word"]) in {"gbt", "gpt", "gpd"}:
            w["word"] = re.sub(r"(?i)cha[td]", "Chat", w["word"], count=1)
            words[i + 1]["word"] = re.sub(r"(?i)gbt|gpt|gpd", "GPT", words[i + 1]["word"], count=1)
    bare = [_bare(w["word"]) for w in words]
    ai = any(b in AI_TALK for b in bare)
    for i, b in enumerate(bare):
        before = bare[i - 1] if i else ""
        after = bare[i + 1] if i + 1 < len(bare) else ""
        stem = b[:-2] if b.endswith("'s") else b
        if b == "school" and after in SKOOL_NEXT and before not in {"high", "middle", "elementary", "law", "med", "medical", "grad", "trade", "real", "estate"}:
            _swap(words[i], "Skool")
        elif b == "whisper" and after == "flow":
            _swap(words[i], "Wispr")
            words[i + 1]["word"] = re.sub("flow", "Flow", words[i + 1]["word"], count=1)
        if stem in {"claud", "clawd"} or (stem == "claude" and not words[i]["word"].strip().startswith("Claude")):
            is_name = True
        elif stem == "clawed":
            is_name = after in NAME_NEXT
        elif stem == "cloud":
            if after in NAME_NEXT or (ai and after in NAME_NEXT_AI):
                is_name = True
            elif before in REAL_BEFORE or after in REAL_AFTER:
                is_name = False
            else:
                is_name = ai or before in NAME_BEFORE
        elif stem == "claude" and before == "the" and after not in NAME_NEXT | NAME_NEXT_AI | {"app", "team", "model", "models", "way"}:
            # the hint at the top of this file can pull a real "the cloud" the other way
            words[i]["word"] = re.sub("Claude", "cloud", words[i]["word"], count=1)
            continue
        else:
            is_name = False
        if is_name:
            _swap(words[i], "Claude")
        if (is_name or stem == "claude") and after in {"core", "coat", "code"}:
            words[i + 1]["word"] = re.sub(r"(?i)core|coat|code", "Code", words[i + 1]["word"], count=1)
    return words


# the person's own ElevenLabs key, if they picked it on the page. It stays in their brand folder on their computer.
SAVED = os.path.join(HOME, "Content Made Easy Brand")


def _eleven_call(path, key):
    return requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key},
                         files={"file": (os.path.basename(path), open(path, "rb"), "audio/mpeg")},
                         data={"model_id": "scribe_v1", "timestamps_granularity": "word", "language_code": "en"}, timeout=(30, 600))


def eleven_try(path, key):
    """Empty when the key works, otherwise what to tell the person."""
    try:
        r = _eleven_call(path, key)
    except Exception:
        return "We couldn't reach ElevenLabs. Check your internet and try again."
    if r.status_code == 200:
        return ""
    if r.status_code in (401, 403):
        return "ElevenLabs said no to that key. Make sure it's turned on for Speech to Text."
    return f"ElevenLabs said {r.status_code}. Try again in a minute."


def eleven(path):
    """Return (words, segments), or None if they didn't pick it or it failed, so this computer takes over."""
    picked = os.path.join(SAVED, "transcription.json")
    if not os.path.exists(picked):
        return None
    try:
        if json.load(open(picked)).get("engine") != "elevenlabs":
            return None
        key = open(os.path.join(SAVED, "elevenlabs.key")).read().strip()
        r = _eleven_call(path, key)
    except Exception as e:
        log(f"   ElevenLabs didn't answer ({type(e).__name__}), this computer takes over")
        return None
    if r.status_code != 200:
        log(f"   ElevenLabs said {r.status_code}, this computer takes over")
        return None
    words = [{"word": w["text"], "start": w["start"], "end": w["end"]} for w in r.json().get("words", []) if w.get("type") == "word"]
    if not words:
        log("   ElevenLabs sent back no words, this computer takes over")
        return None
    return fix_names(words), [{"start": words[0]["start"], "end": words[-1]["end"], "text": " ".join(w["word"] for w in words)}]
