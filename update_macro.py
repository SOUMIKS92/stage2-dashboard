"""
update_macro.py
===============
Standalone script run by GitHub Actions (.github/workflows/refresh-macro.yml).
Fetches a small set of macro indicators via yfinance and writes/updates
macro.json in the repo root.

Failure-tolerant:
- If yfinance returns nothing for a symbol, the prior value is preserved.
- If yfinance is fully blocked (rare on GitHub IPs), the script exits 0 with
  no commit; the prior macro.json stays in place. The dashboard never breaks.
"""
from __future__ import annotations
import datetime as dt, json, os, sys, time

TICKERS = {
    "US10Y": "^TNX",
    "DXY":   "DX-Y.NYB",
    "VIX":   "^VIX",
    "Brent": "BZ=F",
    "SPX":   "^GSPC",
    "Gold":  "GC=F",
}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macro.json")


def load_prev():
    if not os.path.exists(OUT): return {"_meta": {}}
    try:
        with open(OUT) as f: return json.load(f)
    except Exception:
        return {"_meta": {}}


def fetch():
    try:
        import yfinance as yf
    except ImportError:
        print("ERR: yfinance not installed", file=sys.stderr); sys.exit(2)

    prev = load_prev()
    out  = {"_meta": {"as_of": dt.date.today().isoformat(),
                      "source": "yfinance (daily, GitHub Action)"}}

    for name, sym in TICKERS.items():
        try:
            h = yf.Ticker(sym).history(period="2mo", interval="1d", auto_adjust=False)
            if h is None or len(h) < 2:
                print(f"  WARN: no data for {sym} — preserving prior")
                out[name] = prev.get(name)
                continue
            last = float(h["Close"].iloc[-1])
            # WoW = compare to ~5 trading days ago (1 week)
            wow_idx = -6 if len(h) >= 6 else -2
            wow_ref = float(h["Close"].iloc[wow_idx])
            year_start = dt.date(dt.date.today().year, 1, 1)
            ytd_slice = h[h.index >= year_start.isoformat()]
            ytd = ((last / float(ytd_slice["Close"].iloc[0]) - 1) * 100) if len(ytd_slice) else None
            out[name] = {
                "ticker":   sym,
                "level":    round(last, 2),
                "wow_chg":  round(last - wow_ref, 2),
                "wow_pct":  round((last/wow_ref - 1) * 100, 2) if wow_ref else None,
                "ytd_pct":  round(ytd, 2) if ytd is not None else None,
            }
            print(f"  [+] {name:6s} {last:>10.2f}  WoW {out[name]['wow_pct']:+.2f}%  YTD {out[name]['ytd_pct'] or 0:>+.2f}%")
            time.sleep(0.3)  # be nice to Yahoo
        except Exception as e:
            print(f"  WARN: {sym} failed: {e} — preserving prior", file=sys.stderr)
            out[name] = prev.get(name)

    # If ALL fetches failed, don't overwrite — keep prior
    real_hits = sum(1 for k, v in out.items() if k != "_meta" and v and v.get("level") is not None
                    and v.get("level") != (prev.get(k) or {}).get("level"))
    if real_hits == 0 and any(prev.get(k) for k in TICKERS):
        print("ERR: no fresh data — keeping prior macro.json (no commit will trigger)", file=sys.stderr)
        sys.exit(0)

    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    fetch()
