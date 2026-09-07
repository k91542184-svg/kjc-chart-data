#!/usr/bin/env python3
"""
KJC 차트용 미국주식 일봉 데이터 수집기
─────────────────────────────────────────────
tickers.txt 를 읽어 yfinance 로 6년치 일봉을 받아
data/<TICKER>.json 과 data/index.json 을 만든다.

- API 키 불필요 (yfinance)
- 6년치인 이유: 일봉 240선(1년), 주봉 240선(4.6년), 월봉 72선(6년)을
  모두 계산할 수 있는 최소 길이
- OHLC 는 액면분할 반영(수정주가), 배당 미반영 — 일반 HTS 차트와 같은 기준
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TICKER_FILE = os.path.join(ROOT, "tickers.txt")

PERIOD = "6y"
MAX_RETRY = 3
SLEEP = 1.2


def read_tickers():
    if not os.path.exists(TICKER_FILE):
        print(f"[!] {TICKER_FILE} 이 없습니다.", file=sys.stderr)
        return []
    out = []
    with open(TICKER_FILE, encoding="utf-8") as f:
        for line in f:
            s = line.split("#")[0].strip().upper()
            if s and s not in out:
                out.append(s)
    return out


def fetch(ticker):
    """일봉 OHLCV 를 [[date, o, h, l, c, v], ...] 로 반환. 실패하면 None."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            df = yf.Ticker(ticker).history(
                period=PERIOD, interval="1d", auto_adjust=False, raise_errors=False
            )
            if df is None or df.empty:
                raise ValueError("빈 응답")

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
                rows.append([
                    idx.strftime("%Y-%m-%d"),
                    round(o, 4), round(h, 4), round(l, 4), round(c, 4), v,
                ])

            if len(rows) < 60:
                raise ValueError(f"행이 너무 적음 ({len(rows)})")
            return rows

        except Exception as e:  # noqa: BLE001 - 어떤 실패든 재시도 대상
            print(f"    시도 {attempt}/{MAX_RETRY} 실패: {e}", file=sys.stderr)
            if attempt < MAX_RETRY:
                time.sleep(SLEEP * attempt * 2)
    return None


def _finite(x):
    return x == x and x not in (float("inf"), float("-inf"))


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    tickers = read_tickers()
    if not tickers:
        print("[!] 수집할 티커가 없습니다.", file=sys.stderr)
        return 1

    os.makedirs(DATA, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index, failed = [], []

    print(f"[i] {len(tickers)}개 티커 · {PERIOD} 일봉 수집 시작")
    for i, tk in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {tk}")
        rows = fetch(tk)
        if rows is None:
            failed.append(tk)
            print(f"    ✗ 실패 — 기존 파일을 유지합니다", file=sys.stderr)
            continue

        write_json(os.path.join(DATA, f"{tk}.json"), {
            "ticker": tk,
            "updated": now,
            "source": "yfinance (Yahoo Finance) · 액면분할 반영 · 배당 미반영",
            "fields": ["t", "o", "h", "l", "c", "v"],
            "rows": rows,
        })
        index.append({
            "t": tk,
            "n": len(rows),
            "from": rows[0][0],
            "to": rows[-1][0],
            "last": rows[-1][4],
        })
        print(f"    ✓ {len(rows)}행 · {rows[0][0]} ~ {rows[-1][0]} · 종가 {rows[-1][4]}")
        time.sleep(SLEEP)

    # 목록에서 빠진 티커의 옛 파일은 남겨두되 index 에서는 제외한다
    write_json(os.path.join(DATA, "index.json"), {
        "updated": now,
        "period": PERIOD,
        "count": len(index),
        "failed": failed,
        "tickers": sorted(index, key=lambda x: x["t"]),
    })

    print(f"\n[i] 성공 {len(index)} · 실패 {len(failed)}")
    if failed:
        print(f"[!] 실패 목록: {', '.join(failed)}", file=sys.stderr)
    # 전부 실패했을 때만 워크플로를 실패로 표시한다
    return 1 if index == [] else 0


if __name__ == "__main__":
    sys.exit(main())
