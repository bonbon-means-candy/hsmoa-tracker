import os
import pandas as pd
from datetime import datetime
from curl_cffi import requests

def collect_bypassed_home_shopping_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    today_nodash = datetime.today().strftime('%Y%m%d')
    print(f"[{today_str}] TLS 차단 우회 엔진 기반 건강식품 편성표 수집 시작...")

    # 건강식품 핵심 키워드
    health_keywords = [
        "유산균", "콜라겐", "비타민", "루테인", "홍삼", "아르기닌", "다이어트", "효소", 
        "콘드로이친", "오메가", "밀크씨슬", "프로틴", "단백질", "글루타치온", "칼슘", 
        "마그네슘", "MSM", "관절", "혈당", "크릴오일", "프로폴리스", "보스웰리아", 
        "침향", "경옥고", "에스더", "정관장", "여에스더", "종근당", "대웅", "CJ웰케어",
        "건강", "진액", "즙", "매스티드", "카무트", "바나바", "모로오렌지", "아스타잔틴",
        "석류", "타트체리", "락토페린", "프리바이오틱스", "프로바이오틱스", "면역", "유기농"
    ]

    exclude_keywords = [
        "김치", "갈비", "돈까스", "만두", "탕", "찌개", "고기", "족발", "사과", "쌀",
        "샴푸", "청소기", "세제", "화장품", "앰플", "크림", "소파", "침대", "원피스", "냄비"
    ]

    items = []
    seen_keys = set()

    # 한국 크롬 브라우저 지문(Fingerprint) 위장 세션 생성
    session = requests.Session(impersonate="chrome120")

    # API 엔드포인트 목록
    urls = [
        f"https://www.nsmall.com/api/schedule/list?broadcastDate={today_nodash}",
        f"https://m.gsshop.com/shop/tv/tvScheduleList.gs?broadcastDate={today_nodash}",
        f"https://www.gongyoungshop.kr/api/schedule/daily?date={today_nodash}"
    ]

    for target_url in urls:
        try:
            res = session.get(target_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                
                schedules = []
                if isinstance(data, list):
                    schedules = data
                elif isinstance(data, dict):
                    schedules = (
                        data.get("scheduleList") or 
                        data.get("list") or 
                        data.get("data") or 
                        data.get("broadcastList") or []
                    )

                for row in schedules:
                    if not isinstance(row, dict):
                        continue

                    title = row.get("prdNm") or row.get("productName") or row.get("goodsName") or row.get("title") or ""
                    title_str = str(title).strip()
                    if not title_str:
                        continue

                    if any(ex in title_str for ex in exclude_keywords):
                        continue

                    if any(kw in title_str for kw in health_keywords):
                        air_time = row.get("broadStartTime") or row.get("startTime") or row.get("airTime") or "시간미표시"
                        time_str = str(air_time)
                        if len(time_str) >= 4 and time_str.isdigit():
                            time_str = f"{time_str[:2]}:{time_str[2:4]}"

                        price = row.get("salePrice") or row.get("price") or row.get("dcPrice") or 0
                        if isinstance(price, (int, float)) and price > 0:
                            price_str = f"{int(price):,}원"
                        else:
                            price_str = str(price) if price else "가격미표시"

                        unique_key = f"{time_str}_{title_str}_{price_str}"
                        if unique_key not in seen_keys:
                            seen_keys.add(unique_key)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": time_str,
                                "품목명": title_str,
                                "가격": price_str
                            })
        except Exception as e:
            print(f"호출 오류 참고 ({target_url}): {e}")

    print(f"오늘 당일 수집된 총 건강식품 방송 건수: {len(items)}건")

    if not items:
        print("수집된 데이터가 없습니다.")
        return

    # CSV 저장 (수집일자, 방송시간, 품목명, 가격)
    df = pd.DataFrame(items)

    os.makedirs("data/daily", exist_ok=True)
    os.makedirs("data/monthly", exist_ok=True)

    daily_path = f"data/daily/hsmoa_{today_str}.csv"
    month_str = datetime.today().strftime('%Y-%m')
    monthly_path = f"data/monthly/hsmoa_{month_str}.csv"

    df.to_csv(daily_path, index=False, encoding="utf-8-sig")
    print(f"일간 데이터 저장 완료: {daily_path}")

    if os.path.exists(monthly_path):
        df_old = pd.read_csv(monthly_path)
        df_merged = pd.concat([df_old, df]).drop_duplicates(subset=["수집일자", "방송시간", "품목명", "가격"])
        df_merged.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(monthly_path, index=False, encoding="utf-8-sig")

if __name__ == "__main__":
    collect_bypassed_home_shopping_schedule()
