import os
import requests
import pandas as pd
from datetime import datetime

def collect_hsmoa_health_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    print(f"[{today_str}] 홈쇼핑모아 API 기반 건강식품 전체 편성표 수집 시작...")

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 HsmoaApp",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://hsmoa.com/"
    }

    items = []
    seen_keys = set()

    # 1. 홈쇼핑모아 모바일 백엔드 API 시도
    api_urls = [
        "https://api.hsmoa.com/v1/schedule",
        "https://api.hsmoa.com/v2/schedule",
        "https://trend.hsmoa-ad.com/api/schedule"
    ]

    # 건강식품 관련 키워드 (화이트리스트 필터링용)
    health_keywords = [
        "유산균", "콜라겐", "비타민", "루테인", "홍삼", "아르기닌", "다이어트", "효소", 
        "콘드로이친", "오메가", "밀크씨슬", "프로틴", "단백질", "글루타치온", "칼슘", 
        "마그네슘", "MSM", "관절", "혈당", "크릴오일", "프로폴리스", "보스웰리아", 
        "침향", "경옥고", "에스더", "정관장", "여에스더", "종근당", "대웅", "CJ웰케어",
        "건강", "진액", "즙", "매스티드", "카무트", "바나바", "모로오렌지", "아스타잔틴",
        "석류", "타트체리", "락토페린", "프리바이오틱스", "프로바이오틱스", "면역"
    ]

    exclude_keywords = [
        "김치", "갈비", "돈까스", "만두", "탕", "찌개", "고기", "족발", "사과", "쌀",
        "샴푸", "청소기", "세제", "화장품", "앰플", "크림", "소파", "침대", "원피스"
    ]

    for url in api_urls:
        try:
            # 카테고리 파라미터 변형 시도
            params_list = [
                {"date": today_str, "category": "건강식품", "site": "all"},
                {"date": today_str, "cate": "health", "site": "all"},
                {"date": today_str, "site": "all"}
            ]

            for params in params_list:
                res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    
                    # JSON 내부 목록 객체 추출
                    schedules = []
                    if isinstance(data, list):
                        schedules = data
                    elif isinstance(data, dict):
                        schedules = data.get("data") or data.get("schedules") or data.get("list") or data.get("result") or []

                    if schedules and isinstance(schedules, list):
                        for item in schedules:
                            if not isinstance(item, dict):
                                continue

                            title = item.get("title") or item.get("product_name") or item.get("goods_name") or item.get("name", "")
                            price = item.get("price") or item.get("goods_price") or item.get("discount_price", "")
                            air_time = item.get("air_time") or item.get("start_time") or item.get("time_str") or item.get("time", "")

                            if title:
                                title_str = str(title).strip()
                                
                                # 일반식품/잡화 제외 및 건강식품 키워드 검증
                                if any(ex in title_str for ex in exclude_keywords):
                                    continue
                                
                                # 전체 편성 데이터에서 건강식품 항목 추출
                                is_health = any(kw in title_str for kw in health_keywords) or ("cate" in params and params["cate"] != "all")
                                
                                if is_health:
                                    if isinstance(price, (int, float)) and price > 0:
                                        price_str = f"{int(price):,}원"
                                    else:
                                        price_str = str(price) if price else "가격미표시"

                                    time_str = str(air_time) if air_time else "시간미표시"

                                    unique_key = f"{time_str}_{title_str}_{price_str}"
                                    if unique_key not in seen_keys:
                                        seen_keys.add(unique_key)
                                        items.append({
                                            "수집일자": today_str,
                                            "방송시간": time_str,
                                            "품목명": title_str,
                                            "가격": price_str
                                        })

                    if len(items) > 10:
                        break
            if len(items) > 10:
                break
        except Exception as e:
            print(f"API 호출 ({url}) 참고: {e}")

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
    collect_hsmoa_health_schedule()
