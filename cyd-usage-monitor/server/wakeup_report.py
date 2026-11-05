"""Deterministic, local-only wake-up receipts. No model calls or remote assets."""
from __future__ import annotations

import datetime as dt
import io
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROVIDERS = (("codex", "ChatGPT / Codex", "#43d9aa"),
             ("antigravity", "Antigravity", "#6ba5ff"),
             ("claude", "Claude Code", "#e29674"))


def reset_label(result: dict, timezone: str) -> str:
    """Convert confirmed epochs; only use raw CLI text in its original zone."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    if result.get("reset_at") is not None:
        try:
            value = dt.datetime.fromtimestamp(float(result["reset_at"]), zone)
            label = value.strftime("%b %d, %I:%M %p %Z")
            return ("Estimated: " if result.get("reset_estimated") else "") + label
        except (ValueError, TypeError, OverflowError, OSError):
            pass
    text = re.sub(r"\s+", " ", str(result.get("reset_text") or "")).strip()
    if text and result.get("reset_timezone") == timezone:
        text = re.sub(r"\s*\([^)]*/[^)]*\)\s*$", "", text)
        return ("CLI reported: " if result.get("reset_source") == "reported" else "") + text[:140] + " · " + timezone
    return "Not confirmed" if result.get("state") in {"sent", "unknown"} else "Not reported"


def image_reset_parts(result: dict, timezone: str, completed_at: str | None = None) -> tuple[str, str]:
    """Compact display with timezone stated once by the report header."""
    if result.get("reset_at") is not None:
        try:
            zone = ZoneInfo(timezone)
            value = dt.datetime.fromtimestamp(float(result["reset_at"]), zone)
            completed = dt.datetime.fromisoformat(str(completed_at).replace("Z", "+00:00")).astimezone(zone) if completed_at else None
            day = "Today" if completed and value.date() == completed.date() else value.strftime("%b %d")
            note = day + (" · Estimated" if result.get("reset_estimated") else " · CLI reported" if result.get("reset_source") == "reported" else "")
            return value.strftime("%I:%M %p").lstrip("0"), note
        except (ValueError, TypeError, OverflowError, OSError, ZoneInfoNotFoundError):
            pass
    text = re.sub(r"\s+", " ", str(result.get("reset_text") or "")).strip()
    if text and result.get("reset_timezone") == timezone:
        text = re.sub(r"\s*\([^)]*/[^)]*\)\s*$", "", text)
        text = text.replace(timezone, "").strip(" ·,()")
        text = re.sub(r"\b(?:EST|EDT|UTC|GMT)(?:[+-]\d{1,2}(?::?\d{2})?)?\b", "", text).strip()
        match = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text, re.I)
        if match:
            hour, minute = int(match[1]), int(match[2])
            if match[3] and 1 <= hour <= 12:
                hour = hour % 12 + (12 if match[3].lower() == "pm" else 0)
            if 0 <= hour < 24 and 0 <= minute < 60:
                tail = text[match.end():].strip(" ,()")
                tail = re.sub(r"^on\s+", "", tail, flags=re.I)
                note = tail[:28] + (" · CLI reported" if result.get("reset_source") == "reported" else "") if tail else ("CLI reported" if result.get("reset_source") == "reported" else "Confirmed")
                return dt.time(hour, minute).strftime("%I:%M %p").lstrip("0"), note
        return text[:60], "CLI reported" if result.get("reset_source") == "reported" else "Confirmed"
    return "N/A", "Unconfirmed" if result.get("state") in {"sent", "unknown"} else "Not reported"


def quota_limit_lines(result: dict, timezone: str, completed_at: str | None = None) -> list[str]:
    """Safe bounded window-specific reasons shared by text and image receipts."""
    lines = []
    for limit in (result.get("quota_limits") or [])[:2]:
        title = {"weekly": "Weekly quota exhausted", "five_hour": "Five-hour quota exhausted"}.get(limit.get("window"))
        if not title: continue
        when, note = image_reset_parts(limit, timezone, completed_at)
        if when != "N/A":
            day = " · " + note if note not in {"Confirmed", "CLI reported"} else ""
            title += " · resets " + when + day
        else: title += " · reset not reported"
        lines.append(title)
    if result.get("failure_kind") == "usage_limit" and not lines:
        lines.append("Usage/rate limit rejected; weekly vs five-hour not confirmed by CLI.")
    return lines


def render_summary(event: dict, timezone: str = "UTC") -> bytes:
    """A compact report: provider sections and aligned account/reset columns."""
    from PIL import Image, ImageDraw, ImageFont
    from functools import lru_cache

    @lru_cache(maxsize=20)
    def font(size): return ImageFont.load_default(size=size)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    def clean(value, limit=500): return re.sub(r"\s+", " ", str(value or "")).replace("—", "-").replace("–", "-").replace("…", "...").strip()[:limit]
    def wrap(value, size, available, maximum=2):
        text, lines = clean(value), []
        while text and len(lines) < maximum:
            low, high = 1, len(text)
            while low < high:
                middle = (low + high + 1) // 2
                if measure.textlength(text[:middle], font=font(size)) <= available: low = middle
                else: high = middle - 1
            cut = low
            if cut < len(text):
                space = text.rfind(" ", 0, cut + 1)
                if space > cut // 2: cut = space
            lines.append(text[:cut].rstrip());text = text[cut:].lstrip()
        if text and lines:
            while lines[-1] and measure.textlength(lines[-1] + "...", font=font(size)) > available: lines[-1] = lines[-1][:-1]
            lines[-1] += "..."
        return lines or ["-"]

    results = event.get("results") or []
    if not isinstance(results, list) or len(results) > 50: raise ValueError("A report must contain at most 50 account outcomes")
    blocks, height = [], 310
    for provider, title, accent in PROVIDERS:
        accounts = [item for item in results if (item.get("provider") or str(item.get("profile_id", "")).split("-", 1)[0]) == provider]
        if not accounts: continue
        blocks.append(("provider", (provider, title, accent, len(accounts)), 85));height += 85
        groups = {}
        for item in accounts: groups.setdefault((item.get("model") or "Model unavailable", item.get("reasoning") or "fixed"), []).append(item)
        for (model, effort), accounts in groups.items():
            models = wrap(model + " · " + effort + " reasoning", 21, 635, 2)
            size = 27 + len(models) * 26
            blocks.append(("model", models, size));height += size
            for item in accounts:
                names = wrap(item.get("label") or item.get("profile_id") or "Account", 29, 570, 2)
                state = {"sent":"Woken", "failed":"Failed", "unknown":"Unconfirmed", "skipped":"Skipped"}.get(item.get("state"), "Unconfirmed")
                color = {"sent":"#217653", "failed":"#ae3e36", "unknown":"#91641d", "skipped":"#68747d"}.get(item.get("state"), "#91641d")
                reasons = [] if item.get("state") == "sent" else wrap(item.get("reason") or "Outcome not confirmed", 21, 570, 2)
                reset, reset_note = image_reset_parts(item, timezone, event.get("created_at"))
                times = wrap(reset, 31, 255, 2)
                notes = wrap(reset_note, 18, 255, 2)
                size = max(34 + len(names)*35 + 27 + len(reasons)*26, 38 + len(times)*37 + len(notes)*24)
                limits = [line for detail in quota_limit_lines(item, timezone, event.get("created_at")) for line in wrap(detail, 19, 895, 2)]
                size += len(limits) * 25
                blocks.append(("account", (names, state, color, reasons, times, notes, limits), size));height += size
        blocks.append(("space", None, 20));height += 20
    height += 95
    if height > 16000: raise ValueError("Report exceeds the image size limit")
    image = Image.new("RGB", (1000, height), "#f4f3ee");draw = ImageDraw.Draw(image)
    def text(x, y, value, size, color="#202e2a"): draw.text((x, y), value, font=font(size), fill=color)
    def right(y, value, size, color="#202e2a"): text(948-measure.textlength(value,font=font(size)),y,value,size,color)
    scheduled = str(event.get("source", "manual")).startswith("schedule:")
    text(48, 30, "CYD USAGE MONITOR", 17, "#64716a")
    right(30, f"{len(results)} ACCOUNTS", 17, "#64716a")
    text(48, 69, "Scheduled wake-up" if scheduled else "Send now", 45)
    context = event.get("run_context") or {}
    for index, line in enumerate(wrap(context.get("schedule_label") if scheduled else "Immediate request", 25, 900, 2)):
        text(48, 130+index*30, line, 25, "#626e67")
    try:
        when = dt.datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).astimezone(ZoneInfo(timezone))
        stamp = when.strftime("%b %d, %Y · %I:%M %p")
    except (KeyError, ValueError, TypeError, ZoneInfoNotFoundError): stamp = "Run summary"
    text(48, 201, stamp, 19, "#626e67")
    right(201, "Times: " + timezone, 18, "#626e67")
    counts = (("sent","woken","#217653"),("skipped","skipped","#68747d"),("failed","failed","#ae3e36"),("unknown","unconfirmed","#91641d"))
    for index, (state, title, color) in enumerate(counts):
        x = 48+index*230
        draw.ellipse((x,258,x+8,266),fill=color)
        text(x+20,249,str(sum(item.get("state")==state for item in results))+" "+title,23,color)
    draw.line((48,293,952,293),fill="#d0d8d0",width=1)
    y = 317
    for kind, content, size in blocks:
        if kind == "provider":
            provider,title,accent,count = content
            draw.rounded_rectangle((48,y+12,102,y+66),radius=9,fill="#17251f")
            with Image.open(Path(__file__).parent/"static"/"providers"/(provider+".png")) as source:
                icon=source.convert("RGBA").resize((36,36),Image.Resampling.LANCZOS);image.paste(icon,(57,y+21),icon)
            text(119,y+21,title,31);right(y+27,str(count)+(" account" if count==1 else " accounts"),19,"#6b776f")
        elif kind == "model":
            for index,line in enumerate(content): text(48,y+index*26,line,21,"#68756c")
            right(y+2,"NEXT 5H RESET",15,"#68756c")
        elif kind == "account":
            names,state,color,reasons,times,notes,limits = content
            top=y+13
            for line in names: text(48,top,line,29);top+=35
            draw.ellipse((49,top+9,56,top+16),fill=color);text(67,top+1,state,19,color);top+=27
            for line in reasons: text(48,top,line,21,"#637068");top+=26
            reset_y=y+14
            for line in times: right(reset_y,line,31);reset_y+=37
            for line in notes: right(reset_y,line,18,"#91641d" if "Estimated" in line else "#68756c");reset_y+=24
            limit_y = y + size - len(limits)*25 - 9
            for line in limits: text(48,limit_y,line,19,"#ae3e36");limit_y+=25
            draw.line((48,y+size-1,952,y+size-1),fill="#dce1d9",width=1)
        y += size
    draw.line((48,y+15,952,y+15),fill="#cbd5cb",width=1)
    text(48,y+35,"One prompt per account. No automatic retries. Estimates are labeled.",18,"#68756c")
    output=io.BytesIO();image.save(output,"JPEG",quality=91,optimize=True)
    return output.getvalue()
