import os
import requests
import pandas as pd
from datetime import datetime

def collect_direct_home_shopping_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    today_nodash = datetime.today().strftime('%Y%m%d')
    print(f"[{today_str}] 주요 TV 홈쇼핑사 개별 엔드포인트 수집 시작...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }

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

    # 주요 홈쇼핑사 오픈 엔드포인트 목록
    endpoints = [
        # NS홈쇼핑 오픈 API
        {"name": "NS홈쇼핑", "url": f"https://www.nsmall.com/api/schedule/list?broadcastDate={today_nodash}"},
        # GS SHOP 편성 API
        {"name": "GSSHOP", "url": f"https://m.gsshop.com/shop/tv/tvScheduleList.gs?broadcastDate={today_nodash}"},
        # 공영쇼핑 오픈 API
        {"name": "공영쇼핑", "url": f"https://www.gongyoungshop.kr/api/schedule/daily?date={today_nodash}"}
    ]

    for ep in endpoints:
        try:
            res = requests.get(ep["url"], headers=headers, timeout=10)
            if res.status_code == 200:
                # JSON 응답 파싱
                try:
                    data = res.json()
                except Exception:
                    continue

                # JSON 내부 리스트 추출 (다양한 데이터 구조 대응)
                schedule_list = []
                if isinstance(data, list):
                    schedule_list = data
                elif isinstance(data, dict):
                    schedule_list = (
                        data.get("scheduleList") or 
                        data.get("list") or 
                        data.get("data") or 
                        data.get("broadcastList") or []
                    )

                for row in schedule_list:
                    if not isinstance(row, dict):
                        continue

                    # 품목명 추출
                    title = (
                        row.get("prdNm") or 
                        row.get("productName") or 
                        row.get("goodsName") or 
                        row.get("title") or ""
                    )
                    title_str = str(title).strip()
                    if not title_str:
                        continue

                    # 제외 키워드 검증
                    if any(ex in title_str for ex in exclude_keywords):
                        continue

                    # 건강식품 판별
                    if any(kw in title_str for kw in health_keywords):
                        # 방송 시간 추출
                        air_time = (
                            row.get("broadStartTime") or 
                            row.get("startTime") or 
                            row.get("airTime") or "시간미표시"
                        )
                        time_str = str(air_time)
                        if len(time_str) >= 4 and time_str.isdigit():
                            time_str = f"{time_str[:2]}:{time_str[2:4]}"

                        # 가격 추출
                        price = (
                            row.get("salePrice") or 
                            row.get("price") or 
                            row.get("dcPrice") or 0
                        )
                        if isinstance(price, (int, float)) and price > 0:
                            price_str = f"{int(price):,}원"
                        else:
                            price_str = str(price) if price else "가격미표시"

                        unique_key = f"{ep['name']}_{time_str}_{title_str}"
                        if unique_key not in seen_keys:
                            seen_keys.add(unique_key)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": time_str,
                                "품목명": title_str,
                                "가격": price_str
                            })
        except Exception as e:
            print(f"{ep['name']} 수집 중 통신 오류 무시: {e}")

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
    collect_direct_home_shopping_schedule()
