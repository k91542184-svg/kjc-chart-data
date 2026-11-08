#!/usr/bin/env python3
"""
KJC 차트용 30분봉 수집기
─────────────────────────────────────────────
tickers.txt(+ 앱 관심종목) 를 읽어 yfinance 로 최근 60일 30분봉(정규장)을 받아
data30/<TICKER>.json 과 data30/index.json 을 만든다.
- 야후는 30분봉을 최근 60일까지만 제공한다.
- 시각은 뉴욕 현지 시각 "YYYY-MM-DD HH:MM" (09:30 ~ 15:30 시작 봉, 하루 13개)
"""
import os, sys, time
from datetime import datetime, timezone
import yfinance as yf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_kjc_data import read_tickers, write_json, _finite, ROOT

DATA30 = os.path.join(ROOT, "data30")
SLEEP = 1.0


def fetch30(tk):
    for attempt in range(1, 4):
        try:
            df = yf.Ticker(tk).history(period="60d", interval="30m", prepost=False,
                                       auto_adjust=False, raise_errors=False)
            if df is None or df.empty:
                raise ValueError("빈 응답")
            try:
                df.index = df.index.tz_convert("America/New_York")
            except Exception:
                pass
            rows = []
            for idx, r in df.iterrows():
                try:
                    o, h, l, c = float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not all(map(_finite, (o, h, l, c))):
                    continue
                v = r.get("Volume", 0)
                try:
                    v = int(v) if _finite(float(v)) else 0
                except (TypeError, ValueError):
                    v = 0
                rows.append([idx.strftime("%Y-%m-%d %H:%M"), round(o, 4), round(h, 4), round(l, 4), round(c, 4), v])
            if len(rows) < 30:
                raise ValueError("행이 너무 적음 (%d)" % len(rows))
            return rows
        except Exception as e:  # noqa: BLE001
            print("    시도 %d/3 실패: %s" % (attempt, e), file=sys.stderr)
            time.sleep(2 * attempt)
    return None


def main():
    tickers = read_tickers()
    os.makedirs(DATA30, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok, meta, failed = [], {}, []
    print("[i] %d개 티커 · 30분봉 60일 수집 시작" % len(tickers))
    for i, tk in enumerate(tickers, 1):
        rows = fetch30(tk)
        if rows is None:
            failed.append(tk); print("[%d/%d] %s ✗" % (i, len(tickers), tk)); continue
        write_json(os.path.join(DATA30, tk + ".json"), {
            "ticker": tk, "updated": now, "source": "yfinance 30분봉 · 정규장 · 뉴욕 시각",
            "fields": ["t", "o", "h", "l", "c", "v"], "rows": rows})
        ok.append(tk); meta[tk] = {"n": len(rows), "from": rows[0][0], "to": rows[-1][0]}
        print("[%d/%d] %s ✓ %d행 %s ~ %s" % (i, len(tickers), tk, len(rows), rows[0][0], rows[-1][0]))
        time.sleep(SLEEP)
    write_json(os.path.join(DATA30, "index.json"), {
        "updated": now, "interval": "30m", "period": "60d", "tickers": sorted(ok), "meta": meta, "failed": failed})
    print("[i] 30분봉 성공 %d · 실패 %d" % (len(ok), len(failed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
