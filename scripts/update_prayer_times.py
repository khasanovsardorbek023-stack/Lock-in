#!/usr/bin/env python3
import json, os, re, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from playwright.sync_api import sync_playwright

REGIONS = {
    "Toshkent shahri": "toshkent",
    "Toshkent viloyati": "nurafshon",
    "Andijon": "andijon",
    "Buxoro": "buxoro",
    "Farg‘ona": "fargona",
    "Jizzax": "jizzax",
    "Namangan": "namangan",
    "Navoiy": "navoiy",
    "Qashqadaryo": "qarshi",
    "Qoraqalpog‘iston": "nukus",
    "Samarqand": "samarqand",
    "Sirdaryo": "guliston",
    "Surxondaryo": "termiz",
    "Xorazm": "urganch",
}

OUT = Path("data/prayer-times.json")
TZ = ZoneInfo("Asia/Tashkent")
now = datetime.now(TZ)
YEAR, MONTH = now.year, now.month
TIME_RE = re.compile(r"\b([01]\d|2[0-3]):[0-5]\d\b")
DAY_RE = re.compile(r"^\s*(\d{1,2})(?:\s|\D)")

def normalize_row(text):
    text = " ".join(text.replace("\xa0", " ").split())
    m = re.match(r"^(\d{1,2})\b", text)
    times = TIME_RE.findall(text)
    # TIME_RE groups only hours due capturing group; use finditer below instead.
    times = [x.group(0) for x in re.finditer(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", text)]
    if not m or len(times) < 6:
        return None
    day = int(m.group(1))
    if day < 1 or day > 31:
        return None
    return day, {
        "Fajr": times[0],
        "Sunrise": times[1],
        "Dhuhr": times[2],
        "Asr": times[3],
        "Maghrib": times[4],
        "Isha": times[5],
    }

def load_existing():
    if not OUT.exists():
        return {"source": "namozvaqti.uz", "updated_at": None, "data": {}}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"source": "namozvaqti.uz", "updated_at": None, "data": {}}

def scrape_region(page, region, slug):
    url = f"https://namozvaqti.uz/oylik/{MONTH}/{slug}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3500)

    # Some visits may show a verification screen. Give it a little extra time.
    title = page.title()
    body = page.locator("body").inner_text(timeout=15000)
    if "verification" in body.lower() or "one moment" in title.lower():
        page.wait_for_timeout(8000)

    rows = []
    for txt in page.locator("tr").all_inner_texts():
        parsed = normalize_row(txt)
        if parsed:
            rows.append(parsed)

    # Fallback for responsive/mobile layouts where rows aren't actual <tr> elements.
    if not rows:
        body = page.locator("body").inner_text()
        for line in body.splitlines():
            parsed = normalize_row(line)
            if parsed:
                rows.append(parsed)

    if not rows:
        raise RuntimeError(f"No monthly prayer rows found at {url}")

    result = {}
    for day, times in rows:
        try:
            d = datetime(YEAR, MONTH, day)
        except ValueError:
            continue
        result[d.strftime("%Y-%m-%d")] = times
    return url, result

def main():
    payload = load_existing()
    payload.setdefault("data", {})
    payload["source"] = "namozvaqti.uz"
    payload["source_note"] = "Book Media Nashr taqvimi (namozvaqti.uz ko‘rsatgan manba)"
    payload["sync_month"] = f"{YEAR}-{MONTH:02d}"
    errors = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="uz-UZ",
            timezone_id="Asia/Tashkent",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        )
        page = context.new_page()
        for region, slug in REGIONS.items():
            try:
                url, rows = scrape_region(page, region, slug)
                payload["data"].setdefault(region, {}).update(rows)
                print(f"OK {region}: {len(rows)} kun")
            except Exception as e:
                errors[region] = str(e)
                print(f"ERROR {region}: {e}", file=sys.stderr)
            time.sleep(1)
        browser.close()

    payload["updated_at"] = datetime.now(TZ).isoformat()
    payload["errors"] = errors
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Don't fail the whole sync when one city is temporarily blocked; existing
    # data remains and the web app still has the AlAdhan fallback.
    if len(errors) == len(REGIONS):
        print("All namozvaqti.uz regions failed; fallback data will remain active.", file=sys.stderr)

if __name__ == "__main__":
    main()
