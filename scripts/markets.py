#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시장 설정층 — 시장별로 갈라지는 부분만 모은다.

US: 유니버스 하드코딩(SPDR 11섹터 + 4지수), 조정종가, $ 통화.
KR: 유니버스 외부 파일(data/kr/sectors.json, Notion 동기화), 실거래가+양수필터, ₩ 통화.
"""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# ── US 유니버스 (구 us-sector-disparity/update_data.py 하드코딩 이전) ──
US_SECTORS = [
    {"ticker": "XLK",  "slug": "XLK",  "name_ko": "정보기술",        "name_en": "Technology Select Sector SPDR ETF",            "theme": "AI·반도체·소프트웨어"},
    {"ticker": "XLC",  "slug": "XLC",  "name_ko": "커뮤니케이션 서비스", "name_en": "Communication Services Select Sector SPDR ETF", "theme": "광고·미디어·플랫폼"},
    {"ticker": "XLY",  "slug": "XLY",  "name_ko": "임의소비재",       "name_en": "Consumer Discretionary Select Sector SPDR ETF", "theme": "소비 사이클·자동차·이커머스"},
    {"ticker": "XLP",  "slug": "XLP",  "name_ko": "필수소비재",       "name_en": "Consumer Staples Select Sector SPDR ETF",       "theme": "경기 둔화 방어·마진"},
    {"ticker": "XLI",  "slug": "XLI",  "name_ko": "산업재",          "name_en": "Industrial Select Sector SPDR ETF",            "theme": "제조·인프라·방산·물류"},
    {"ticker": "XLB",  "slug": "XLB",  "name_ko": "소재",            "name_en": "Materials Select Sector SPDR ETF",             "theme": "원자재·화학·금속"},
    {"ticker": "XLE",  "slug": "XLE",  "name_ko": "에너지",          "name_en": "Energy Select Sector SPDR ETF",                "theme": "유가·정제마진·현금흐름"},
    {"ticker": "XLF",  "slug": "XLF",  "name_ko": "금융",            "name_en": "Financial Select Sector SPDR ETF",             "theme": "금리·신용·자본시장"},
    {"ticker": "XLV",  "slug": "XLV",  "name_ko": "헬스케어",        "name_en": "Health Care Select Sector SPDR ETF",           "theme": "방어 성장·정책 리스크"},
    {"ticker": "XLU",  "slug": "XLU",  "name_ko": "유틸리티",        "name_en": "Utilities Select Sector SPDR ETF",             "theme": "전력수요·배당·금리"},
    {"ticker": "XLRE", "slug": "XLRE", "name_ko": "부동산",          "name_en": "Real Estate Select Sector SPDR ETF",           "theme": "금리·REITs·배당"},
]
US_INDICES = [
    {"ticker": "^GSPC", "slug": "GSPC", "name_ko": "S&P 500",   "name_en": "S&P 500 Index",                "theme": "미국 대형주 500"},
    {"ticker": "^IXIC", "slug": "IXIC", "name_ko": "나스닥 종합", "name_en": "Nasdaq Composite Index",       "theme": "기술주 중심 종합지수"},
    {"ticker": "^DJI",  "slug": "DJI",  "name_ko": "다우존스",    "name_en": "Dow Jones Industrial Average", "theme": "대형 우량주 30"},
    {"ticker": "^RUT",  "slug": "RUT",  "name_ko": "러셀 2000",   "name_en": "Russell 2000 Index",           "theme": "미국 소형주 2000"},
]

MARKETS = {
    "us": {
        "market_id": "us",
        "out_dir": DATA / "us",
        "auto_adjust": True,
        "positive_only": False,
        "currency": {"symbol": "$", "decimals": 2},
        "universe": {"kind": "literal", "sectors": US_SECTORS, "indices": US_INDICES},
        "labels": {
            "site_title": "미국 섹터 ETF 이격도 트래커",
            "subtitle": "미국 주요 지수 + GICS 11개 섹터 SPDR ETF · 100일 이격도 기반 (이그전 해석법)",
            "index_heading": "미국 주요 지수",
        },
    },
    "kr": {
        "market_id": "kr",
        "out_dir": DATA / "kr",
        "auto_adjust": False,
        "positive_only": True,
        "currency": {"symbol": "₩", "decimals": 0},
        "universe": {"kind": "file", "path": DATA / "kr" / "sectors.json"},
        "labels": {
            "site_title": "한국 섹터 ETF 이격도 트래커",
            "subtitle": "코스피·코스닥 + 한국 섹터 ETF · 100일 이격도 기반 (이그전 해석법)",
            "index_heading": "한국 주요 지수 (코스피·코스닥)",
        },
    },
}


def resolve_universe(cfg: dict) -> tuple:
    """시장 설정에서 (sectors, indices)를 얻는다. KR 파일 없으면 기존 fatal 의미 유지."""
    u = cfg["universe"]
    if u["kind"] == "literal":
        return u["sectors"], u["indices"]
    p = u["path"]
    if not p.exists():
        raise SystemExit(f"{p} 없음 — Notion 동기화(scripts/sync_from_notion.py)를 먼저 실행하세요.")
    c = json.loads(p.read_text(encoding="utf-8"))
    return c.get("sectors", []), c.get("indices", [])
