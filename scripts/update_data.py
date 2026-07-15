#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이격도 트래커 드라이버 — 시장을 돌며 수집한다.

사용:  python scripts/update_data.py [us] [kr]   (인자 없으면 us kr 둘 다)

시장별로 격리 실행한다: KR 유니버스 파일 누락(SystemExit) 등 한 시장의 실패가
다른 시장 수집을 중단시키지 않는다. 하나라도 실패하면 비정상 종료코드를 반환한다.
"""

import sys

import core
from markets import MARKETS, resolve_universe


def main():
    targets = [a.lower() for a in sys.argv[1:]] or ["us", "kr"]
    rc = 0
    done = []
    for mid in targets:
        cfg = MARKETS.get(mid)
        if cfg is None:
            print(f"[{mid}] 알 수 없는 시장 — 건너뜀", file=sys.stderr)
            rc = 2
            continue
        try:
            sectors, indices = resolve_universe(cfg)
            n_s, n_i, errors = core.run_market(cfg, sectors, indices)
            done.append(f"{mid}(섹터 {n_s}·지수 {n_i})")
            if errors:
                rc = 2
        except SystemExit as e:  # KR sectors.json 누락 등 — 격리
            print(f"[{mid}] 건너뜀: {e}", file=sys.stderr)
            rc = 2
        except Exception as e:  # noqa: BLE001
            print(f"[{mid}] 실패: {e}", file=sys.stderr)
            rc = 2

    if not done:
        print("수집된 시장이 하나도 없습니다. 중단.", file=sys.stderr)
        sys.exit(1)
    print(f"\n전체 완료: {', '.join(done)}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
