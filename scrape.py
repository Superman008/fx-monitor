#!/usr/bin/env python3
"""Fetch BOC + Moneychain rates and write docs/data/latest.json + history.json."""
import json, os, re, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MEL = ZoneInfo("Australia/Melbourne")
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "docs" / "data"
DEBUG = ROOT / "debug"
BOC_URL = "https://www.boc.cn/sourcedb/whpj/"
MC_URL = "https://www.moneychain.com.au/exchange-rates/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
BAND = (0.92, 1.08)  # Moneychain rate must be within +-8% of the BOC rate, else treated as suspect


def gate(force):
    now = datetime.now(MEL)
    ok = force == "true" or (now.weekday() < 5 and 9 <= now.hour <= 17)
    print(f"Melbourne now: {now:%a %H:%M} -> run={ok}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if ok else 'false'}\n")


def parse_boc(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    idx_rate, idx_pub, found = 5, 6, {}
    for tr in soup.select("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if "货币名称" in cells:
            idx_rate = cells.index("中行折算价")
            idx_pub = cells.index("发布日期")
        elif cells and cells[0] in ("美元", "澳大利亚元") and len(cells) > idx_pub:
            found[cells[0]] = (float(cells[idx_rate]), cells[idx_pub])
    if "美元" not in found or "澳大利亚元" not in found:
        raise ValueError("BOC: USD/AUD rows not found")
    return {"usd": found["美元"][0], "aud": found["澳大利亚元"][0],
            "published_at": found["美元"][1], "published_tz": "北京时间"}


def fetch_boc():
    import requests
    last = None
    for i in range(3):
        try:
            r = requests.get(BOC_URL, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            return parse_boc(r.text)
        except Exception as e:
            last = e
            time.sleep(5)
    raise last


NUM_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def parse_moneychain_html(html):
    """Return rows parsed from the <tr> table: label text, VIP flag, cell numbers."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:  # current 现汇买入价 / 现汇卖出价 columns
            continue
        label = " ".join(cells[0].get_text(" ", strip=True).split())
        nums = []
        for c in cells[1:]:
            t = c.get_text(" ", strip=True).replace(",", "")
            if NUM_RE.fullmatch(t):
                nums.append(float(t))
        if len(nums) < 2:
            continue
        rows.append({"label": label,
                     "vip": bool(tr.select(".vip_huilv")) or "VIP汇率" in label,
                     "buy": nums[0], "sell": nums[1]})
    text = soup.get_text(" ", strip=True)
    m = re.search(r"(\d{2}-\d{2}),?\s*(\d{2}:\d{2})(?::\d{2})?\s*[（(]([^）)]*)[）)]", text)
    return {"rows": rows, "quoted_at": f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else None}


def fetch_moneychain():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(locale="zh-CN", timezone_id="Australia/Melbourne",
                                   user_agent=UA, viewport={"width": 1400, "height": 1000}).new_page()
        page.goto(MC_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_function(r"/美金\s*→\s*人民币/.test(document.body.innerText) && /\d\.\d{4}/.test(document.body.innerText)", timeout=30000)
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()

    res = parse_moneychain_html(html)

    def pick(label, must_vip=False):
        rows = [r for r in res["rows"]
                if r["label"].replace(" ", "").startswith(label) and "人民币" in r["label"]]
        if must_vip:
            rows = [r for r in rows if r["vip"]]
        else:
            rows = [r for r in rows if r["vip"]] or rows
        if not rows:
            raise ValueError(f"Moneychain: row {label}→人民币 not found (must_vip={must_vip})")
        return max(rows, key=lambda r: r["sell"]), rows[0]["vip"]

    aud, aud_vip = pick("澳元", must_vip=True)
    usd, usd_vip = pick("美金")
    for r in (aud, usd):
        if not (r["buy"] and r["sell"] and r["sell"] > r["buy"]):
            raise ValueError(f"Moneychain: unexpected numbers {r}")
    if not aud_vip:  # keep evidence so the selector can be fixed
        DEBUG.mkdir(exist_ok=True)
        (DEBUG / "moneychain.html").write_text(html, encoding="utf-8")
        (DEBUG / "moneychain_rows.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        raise ValueError("Moneychain: VIP tag not matched to 澳元→人民币 row; refusing to publish possibly non-VIP price")
    return {"quoted_at": res["quoted_at"], "aud_vip_buy": aud["buy"], "aud_vip_sell": aud["sell"],
            "usd_buy": usd["buy"], "usd_sell": usd["sell"], "usd_is_vip": usd_vip}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    now = datetime.now(MEL).isoformat(timespec="seconds")
    prev = load(DATA / "latest.json", {})
    out = {"collected_at": now, "seed": False}
    for key, fn in (("boc", fetch_boc), ("moneychain", fetch_moneychain)):
        old = dict(prev.get(key, {}))
        try:
            new = fn()
            out[key] = {**new, "ok": True, "error": None, "last_success": now}
        except Exception as e:
            print(f"{key} failed: {e}", file=sys.stderr)
            out[key] = {**old, "ok": False, "error": str(e)[:300]}
    # sanity check Moneychain against BOC (per-1 units)
    b, m = out["boc"], out["moneychain"]
    if m.get("ok") and b.get("aud") and b.get("usd"):
        for name, mc, bank in (("AUD", m["aud_vip_sell"], b["aud"] / 100), ("USD", m["usd_sell"], b["usd"] / 100)):
            if not BAND[0] <= mc / bank <= BAND[1]:
                out["moneychain"] = {**prev.get("moneychain", {}), "ok": False,
                                     "error": f"{name} price {mc} deviates >8% from BOC {bank:.4f}; not published"}
                break
    (DATA).mkdir(parents=True, exist_ok=True)
    (DATA / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = load(DATA / "history.json", [])
    b, m = out["boc"], out["moneychain"]
    hist.append({"t": now,
                 "boc_usd": b.get("usd") if b.get("ok") else None, "boc_aud": b.get("aud") if b.get("ok") else None,
                 "mc_aud_vip_sell": m.get("aud_vip_sell") if m.get("ok") else None,
                 "mc_usd_sell": m.get("usd_sell") if m.get("ok") else None})
    (DATA / "history.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    if not b["ok"] and not m["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gate":
        gate(sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        main()
