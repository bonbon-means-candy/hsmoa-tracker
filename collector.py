import os
import requests
import pandas as pd
from datetime import datetime

def collect_naver_tvhs_health_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    today_nodash = datetime.today().strftime('%Y%m%d')
    print(f"[{today_str}] 네이버 쇼핑 라이브 기반 TV홈쇼핑 건강식품 편성표 수집 시작...")

    # 네이버 쇼핑 라이브 TV홈쇼핑 방송 편성표 API
    url = "https://shoppinglive.naver.com/api/v1/tv/schedules"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://shoppinglive.naver.com/tv"
    }

    params = {
        "date": today_nodash,
        "page": 1,
        "size": 300
    }

    items = []
    seen_keys = set()

    # 건강식품 식별 키워드 (카테고리명 미표시 대비 이중 검증)
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

    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            schedules = data.get("list", []) or data.get("content", []) or data.get("data", [])
            
            # API 내부 데이터 탐색
            if not schedules and isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list) and len(v) > 0:
                        schedules = v
                        break

            for item in schedules:
                if not isinstance(item, dict):
                    continue

                # 방송 및 상품 정보 파싱
                title = item.get("title") or item.get("productName") or item.get("broadcastTitle", "")
                channel = item.get("channelName") or item.get("broadcastChannel", "")
                
                # 방송 시간
                start_time = item.get("startTime") or item.get("broadcastStartTime", "")
                if start_time and "T" in str(start_time):
                    time_str = str(start_time).split("T")[1][:5]
                elif start_time and len(str(start_time)) >= 4:
                    time_str = str(start_time)[-4:-2] + ":" + str(start_time)[-2:]
                else:
                    time_str = str(start_time) if start_time else "시간미표시"

                # 가격 정보
                price = item.get("price") or item.get("discountPrice") or item.get("salePrice", 0)
                if isinstance(price, (int, float)) and price > 0:
                    price_str = f"{int(price):,}원"
                else:
                    price_str = str(price) if price else "가격미표시"

                # 카테고리 정보
                category = item.get("categoryName") or item.get("category", "")

                title_str = str(title).strip()
                if not title_str:
                    continue

                # 일반식품/잡화 제외
                if any(ex in title_str for ex in exclude_keywords):
                    continue

                # 건강식품 판별 (카테고리명 기준 또는 품목명 키워드 기준)
                is_health = "건강" in str(category) or any(kw in title_str for kw in health_keywords)

                if is_health:
                    unique_key = f"{channel}_{time_str}_{title_str}_{price_str}"
                    if unique_key not in seen_keys:
                        seen_keys.add(unique_key)
                        items.append({
                            "수집일자": today_str,
                            "방송시간": time_str,
                            "품목명": title_str,
                            "가격": price_str
                        })

    except Exception as e:
        print(f"네이버 쇼핑 라이브 API 수집 중 오류: {e}")

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
    collect_naver_tvhs_health_schedule()
