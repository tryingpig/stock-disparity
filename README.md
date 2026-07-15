# 섹터 ETF 이격도 트래커 — 미국 · 한국 (stock-disparity)

미국 SPDR 11개 섹터 + 코스피·코스닥/한국 섹터 ETF의 **100일 이격도**를 매일 자동 추적하고,
**한 페이지에서 상단 메뉴로 미국(US)/한국(KR)을 전환**해 보는 정적 대시보드입니다.

🔗 https://tryingpig.github.io/stock-disparity/  (마지막 본 시장 기억, 첫 방문은 미국)

## 이격도

```
이격도(%) = 당일 종가 ÷ 100일 이동평균 × 100
```
구간(이그전 코스피 기준값, 전 시장 공통): 과열 ≥130 / 경계 120–130 / 정상 105–120 / 과열 해소 ≤105.
이격도는 비율이라 통화(₩/$)와 무관하다.

## 구조

| 파일 | 역할 |
|------|------|
| `scripts/core.py` | 시장 무관 공용 로직(수집·이격도·추세 판정·`run_market`) |
| `scripts/markets.py` | 시장 설정층 — US(하드코딩 유니버스·$·조정종가) / KR(Notion 유니버스·₩·실거래가+양수필터) |
| `scripts/update_data.py` | 드라이버: `python scripts/update_data.py us kr` (시장별 격리 실행) |
| `scripts/sync_from_notion.py` | Notion 'ETF Sector DB' → `data/kr/sectors.json` (KR 유니버스) |
| `index.html` / `detail.html` / `assets/` | 단일 페이지 + 상단 US/KR 메뉴, 통화는 `summary.json`의 `currency`로 주입 |
| `.github/workflows/update.yml` | 한·미 장시간 cron + Notion 동기화 + 양 시장 수집·커밋 |

데이터는 시장별로 분리: `data/us/summary.json`·`data/us/{ticker}.json`, `data/kr/...`.

## 로컬 실행

```bash
pip install -r requirements.txt
# KR 유니버스는 data/kr/sectors.json 필요 (없으면 Notion 동기화):
#   NOTION_TOKEN=... python scripts/sync_from_notion.py
python scripts/update_data.py us kr      # data/us · data/kr 생성
python -m http.server 8000               # http://localhost:8000/index.html?market=us|kr
```

> 정보 제공용이며 투자 권유가 아닙니다.
