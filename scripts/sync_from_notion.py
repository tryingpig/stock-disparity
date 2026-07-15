#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Notion 'ETF Sector DB' → data/kr/sectors.json 생성 (한국 시장 유니버스).

update_data.py(KR)가 읽는 추적 대상 목록(섹터 ETF + 지수)을 Notion DB에서 받아
data/kr/sectors.json으로 쓴다. GitHub Actions에서 데이터 수집 직전에 실행되어
Notion 편집이 매 수집분에 반영되게 한다.

- 대상: 프로젝트=ko-disparity, 활성=True 행. 역할 tracked-etf → sectors, index → indices.
- 정렬: 정렬순서(오름차순) → 티커.
- 토큰: 환경변수 NOTION_TOKEN (Actions Secret).
- Notion 조회 실패 시: 기존 sectors.json이 있으면 그대로 두고 경고만(폴백), 없으면 실패.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

DB_ID = "393ebba0843a80148f6cf99d09012bcc"
BASE = "https://api.notion.com/v1"
OUT = Path(__file__).resolve().parent.parent / "data" / "kr" / "sectors.json"


def api(method, path, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def _rt(prop):
    if not prop:
        return ""
    arr = prop.get("rich_text") or prop.get("title") or []
    return "".join(t.get("plain_text", "") for t in arr).strip()


def fetch_rows(token):
    rows, cursor = [], None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        res = api("POST", f"/databases/{DB_ID}/query", token, payload)
        for r in res["results"]:
            p = r["properties"]
            rows.append({
                "name_ko": _rt(p.get("이름")),
                "name_en": _rt(p.get("영문명")),
                "ticker": _rt(p.get("티커코드")),
                "slug": _rt(p.get("slug")),
                "theme": _rt(p.get("대표ETF")),
                "role": (p.get("역할", {}).get("select") or {}).get("name", ""),
                "projects": [o["name"] for o in p.get("프로젝트", {}).get("multi_select", [])],
                "order": p.get("정렬순서", {}).get("number"),
                "active": p.get("활성", {}).get("checkbox", False),
            })
        if not res.get("has_more"):
            break
        cursor = res["next_cursor"]
    return rows


def build(rows):
    def keep(role):
        items = [r for r in rows if r["active"] and "ko-disparity" in r["projects"] and r["role"] == role]
        items.sort(key=lambda r: (r["order"] if r["order"] is not None else 1e9, r["ticker"]))
        return [{
            "ticker": r["ticker"], "slug": r["slug"],
            "name_ko": r["name_ko"], "name_en": r["name_en"], "theme": r["theme"],
        } for r in items]

    return {"sectors": keep("tracked-etf"), "indices": keep("index")}


def main():
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        # 토큰 없으면: 기존 파일 있으면 폴백, 없으면 실패
        if OUT.exists():
            print("NOTION_TOKEN 없음 → 기존 sectors.json 유지(폴백)", file=sys.stderr)
            return
        sys.exit("NOTION_TOKEN 환경변수가 필요합니다.")

    try:
        rows = fetch_rows(token)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        if OUT.exists():
            print(f"Notion 조회 실패({e}) → 기존 sectors.json 유지(폴백)", file=sys.stderr)
            return
        sys.exit(f"Notion 조회 실패, 폴백 파일도 없음: {e}")

    cfg = build(rows)
    if not cfg["sectors"]:
        # 방어: 섹터 0개면 뭔가 잘못된 것 → 기존 파일 보존
        if OUT.exists():
            print("섹터 0개 수신 → 기존 sectors.json 유지(폴백)", file=sys.stderr)
            return
        sys.exit("섹터 0개 수신, 폴백 파일도 없음. 중단.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sectors.json 생성: 섹터 {len(cfg['sectors'])} · 지수 {len(cfg['indices'])}")


if __name__ == "__main__":
    main()
