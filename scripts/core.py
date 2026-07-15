#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이격도 트래커 공용 코어 — 수집/계산/판정 로직 (시장 무관).

us-sector-disparity / ko-disparity에서 동일했던 로직을 여기로 모으고,
시장별로 갈라지던 두 지점만 파라미터로 뽑았다:
  · fetch_history(auto_adjust, positive_only) — US=조정종가 / KR=실거래가+양수필터
  · process_entry(out_dir)                    — 시장별 data/{market}/ 로 출력
run_market()은 한 시장을 통째로 처리하고 summary.json에 currency·labels를 실어 준다.
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# ── 공통 설정 ─────────────────────────────────────────────────────────
MA_SHORT = 10           # 단기 이동평균 (상승장 판정용, 전 시장 공통)
MA_MID = 20             # 중기 이동평균 (상승장 판정용, 전 시장 공통)
MA_SLOPE_LOOKBACK = 5   # 이평선 기울기 판정 기준(거래일)
# 이격도 기준 이동평균 기간은 시장별로 다르다(markets.py: US=100 / KR=50) → run_market 인자로 받는다.
HISTORY_PERIOD = "6y"   # 수집 범위 (5Y 토글 + MA100 워밍업 여유)
SERIES_KEEP_DAYS = 1300 # {티커}.json 보관 최근 거래일 수 (약 5년)

# 구간 임계값 (고정, 전 시장 공통 — 이그전 코스피 기준값)
ZONE_COOLDOWN_MAX = 105   # <=105 : 과열 해소
ZONE_NORMAL_MAX = 120     # 105~120 : 정상
ZONE_WARNING_MAX = 130    # 120~130 : 경계, >=130 : 과열

KST = timezone(timedelta(hours=9))


def classify_zone(disparity: float) -> str:
    """이격도 값을 구간 코드로 변환한다."""
    if disparity >= ZONE_WARNING_MAX:
        return "overheated"
    if disparity >= ZONE_NORMAL_MAX:
        return "warning"
    if disparity >= ZONE_COOLDOWN_MAX:
        return "normal"
    return "cooldown"


def fetch_history(ticker: str, *, auto_adjust: bool, positive_only: bool = False,
                  retries: int = 3) -> pd.DataFrame:
    """yfinance 일봉 종가를 받는다. 실패 시 재시도.

    auto_adjust  : US=True(조정종가). KR=False(실거래가 — 일부 ETF 조정종가 이상치 회피).
    positive_only: True면 음수·0 종가를 필터(KR 방어).
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.Ticker(ticker).history(period=HISTORY_PERIOD, interval="1d", auto_adjust=auto_adjust)
            if df is not None and not df.empty and "Close" in df.columns:
                if positive_only:
                    df = df[df["Close"] > 0]
                if not df.empty:
                    return df
            last_err = f"빈 데이터 (시도 {attempt})"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(2 * attempt)
    raise RuntimeError(f"{ticker} 수집 실패: {last_err}")


def compute_series(df: pd.DataFrame, ma_period: int) -> pd.DataFrame:
    """종가에서 MA10/20 + 기준 이동평균(ma_period)과 이격도를 계산한다.

    'ma' 컬럼 = 이격도 기준 이동평균(기간중립 키). 이격도 = 종가/ma*100.
    """
    out = pd.DataFrame(index=df.index)
    close = df["Close"]
    out["price"] = close.round(2)
    out["ma10"] = close.rolling(window=MA_SHORT, min_periods=MA_SHORT).mean().round(2)
    out["ma20"] = close.rolling(window=MA_MID, min_periods=MA_MID).mean().round(2)
    out["ma"] = close.rolling(window=ma_period, min_periods=ma_period).mean().round(2)
    out["disparity"] = (close / out["ma"] * 100).round(2)
    out = out.dropna(subset=["ma", "disparity"])
    return out


def classify_market(series: pd.DataFrame, lookback: int = MA_SLOPE_LOOKBACK) -> dict:
    """최신 시점 추세를 10·20일선으로 판정한다(할투 추세추종 규칙).

    상승장 = 10일선 상승 & 20일선 상승 & 10일선 > 20일선
    하락장 = 10일선 하락 & 20일선 하락 & 10일선 < 20일선
    그 외   = 횡보장. score(-100~100)는 게이지 바늘용 추세 강도.
    """
    if len(series) <= lookback:
        return None
    ma10, ma20 = series["ma10"], series["ma20"]
    n10, n20 = float(ma10.iloc[-1]), float(ma20.iloc[-1])
    p10, p20 = float(ma10.iloc[-1 - lookback]), float(ma20.iloc[-1 - lookback])
    up10, up20, cross = n10 > p10, n20 > p20, n10 > n20
    if up10 and up20 and cross:
        state, label = "bull", "상승장"
    elif (not up10) and (not up20) and (not cross):
        state, label = "bear", "하락장"
    else:
        state, label = "sideways", "횡보장"

    spread = (n10 - n20) / n20 * 100
    s10 = (n10 / p10 - 1) * 100
    s20 = (n20 / p20 - 1) * 100

    def clamp(x, lo, hi):
        return max(lo, min(hi, x))

    score = (0.4 * clamp(spread / 2.0, -1, 1)
             + 0.3 * clamp(s10 / 3.0, -1, 1)
             + 0.3 * clamp(s20 / 2.0, -1, 1)) * 100
    return {
        "state": state, "label": label, "score": round(score, 1),
        "cross": cross, "up10": up10, "up20": up20,
        "spread_pct": round(spread, 2), "slope10_pct": round(s10, 2), "slope20_pct": round(s20, 2),
    }


def process_entry(meta: dict, kind: str, out_dir: Path, *,
                  auto_adjust: bool, positive_only: bool, ma_period: int) -> dict:
    """티커 하나를 수집·계산하고 out_dir/{slug}.json을 쓴 뒤 summary 스냅샷을 반환."""
    symbol = meta["ticker"]
    file_id = meta.get("slug", symbol)

    df = fetch_history(symbol, auto_adjust=auto_adjust, positive_only=positive_only)
    series = compute_series(df, ma_period)
    if series.empty:
        raise RuntimeError(f"MA{ma_period} 계산 가능한 데이터 부족")

    last = series.iloc[-1]
    as_of_date = series.index[-1].strftime("%Y-%m-%d")
    disparity = float(last["disparity"])
    market = classify_market(series)

    tail = series.tail(SERIES_KEEP_DAYS)
    payload = {
        "ticker": file_id, "symbol": symbol, "kind": kind,
        "name_ko": meta["name_ko"], "name_en": meta["name_en"], "theme": meta["theme"],
        "ma_period": ma_period, "ma_periods": [MA_SHORT, MA_MID, ma_period],
        "slope_lookback": MA_SLOPE_LOOKBACK, "market": market,
        "series": [
            {"date": idx.strftime("%Y-%m-%d"), "price": float(row["price"]),
             "ma10": float(row["ma10"]), "ma20": float(row["ma20"]),
             "ma": float(row["ma"]), "disparity": float(row["disparity"])}
            for idx, row in tail.iterrows()
        ],
    }
    (out_dir / f"{file_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    mlabel = market["label"] if market else "-"
    print(f"    [OK] {symbol:10s} 이격도 {disparity:6.2f}%  ({classify_zone(disparity)})  추세 {mlabel}  as_of {as_of_date}")
    return {
        "ticker": file_id, "symbol": symbol, "kind": kind,
        "name_ko": meta["name_ko"], "name_en": meta["name_en"], "theme": meta["theme"],
        "price": float(last["price"]), "ma10": float(last["ma10"]),
        "ma20": float(last["ma20"]), "ma": float(last["ma"]),
        "disparity": disparity, "zone": classify_zone(disparity),
        "market": market, "as_of_date": as_of_date,
    }


def run_market(cfg: dict, sectors: list, indices: list) -> tuple:
    """한 시장을 통째로 수집·계산하고 out_dir/summary.json을 쓴다.

    반환: (성공 섹터수, 성공 지수수, 실패 티커 리스트).
    한 시장 실패가 다른 시장을 죽이지 않도록 sys.exit 대신 값을 반환한다.
    """
    out_dir = cfg["out_dir"]
    ma_period = cfg["ma_period"]
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(KST)
    summary_sectors, summary_indices, errors = [], [], []

    print(f"  [{cfg['market_id']}] 지수 수집… (MA{ma_period})")
    for meta in indices:
        try:
            summary_indices.append(process_entry(meta, "index", out_dir,
                                                  auto_adjust=cfg["auto_adjust"], positive_only=cfg["positive_only"],
                                                  ma_period=ma_period))
        except Exception as e:  # noqa: BLE001
            errors.append(meta["ticker"])
            print(f"    [FAIL] {meta['ticker']}: {e}", file=sys.stderr)

    print(f"  [{cfg['market_id']}] 섹터 수집… (MA{ma_period})")
    for meta in sectors:
        try:
            summary_sectors.append(process_entry(meta, "sector", out_dir,
                                                 auto_adjust=cfg["auto_adjust"], positive_only=cfg["positive_only"],
                                                 ma_period=ma_period))
        except Exception as e:  # noqa: BLE001
            errors.append(meta["ticker"])
            print(f"    [FAIL] {meta['ticker']}: {e}", file=sys.stderr)

    if not summary_sectors:
        raise RuntimeError(f"[{cfg['market_id']}] 수집된 섹터가 하나도 없습니다.")

    summary_sectors.sort(key=lambda s: s["disparity"], reverse=True)
    for i, s in enumerate(summary_sectors, start=1):
        s["rank"] = i

    all_dates = [s["as_of_date"] for s in summary_sectors] + [s["as_of_date"] for s in summary_indices]
    as_of = max(all_dates)
    summary = {
        "market": cfg["market_id"],
        "currency": cfg["currency"],
        "labels": cfg["labels"],
        "updated_at": now.isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "ma_period": ma_period, "ma_periods": [MA_SHORT, MA_MID, ma_period],
        "slope_lookback": MA_SLOPE_LOOKBACK,
        "zones": {
            "cooldown_max": ZONE_COOLDOWN_MAX, "normal_max": ZONE_NORMAL_MAX, "warning_max": ZONE_WARNING_MAX,
        },
        "indices": summary_indices,
        "sectors": summary_sectors,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [{cfg['market_id']}] 완료: 지수 {len(summary_indices)}/{len(indices)} · 섹터 {len(summary_sectors)}/{len(sectors)}, as_of {as_of}")
    return len(summary_sectors), len(summary_indices), errors
