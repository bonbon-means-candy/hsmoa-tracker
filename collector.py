import os
import requests
import pandas as pd
from datetime import datetime

def collect_hsmoa_health_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    print(f"[{today_str}] 홈쇼핑모아 API 기반 건강식품 전체 편성표 수집 시작...")

    # 홈쇼핑모아 메인 백엔드 API 엔드포인트
    # category: 건강식품 / date: YYYY-MM-DD
    url = "https://api.hsmoa.com/v1/schedule"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 HsmoaApp",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://hsmoa.com/"
    }

    params = {
        "date": today_str,
        "category": "건강식품",
        "site": "all"
    }

    items = []
    seen_keys = set()

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        
        # 메인 API 구조에 맞춰 파싱 (실패 시 fallback 백업 API 시도)
        if response.status_code == 200:
            data = response.json()
            
            # JSON 데이터 내 방송 목록 탐색 (list, data, schedule_list 등)
            raw_schedules = data.get("data", []) if isinstance(data, dict) else data
            if isinstance(data, dict) and not raw_schedules:
                raw_schedules = data.get("schedules", []) or data.get("list", []) or data.get("result", [])

            for item in raw_schedules:
                if not isinstance(item, dict):
                    continue

                # API 필드 파싱
                title = item.get("title") or item.get("product_name") or item.get("goods_name") or item.get("name", "")
                price = item.get("price") or item.get("goods_price") or item.get("discount_price", "")
                air_time = item.get("air_time") or item.get("start_time") or item.get("time_str") or item.get("time", "")
                channel = item.get("site") or item.get("channel") or item.get("company", "")

                if title:
                    # 가격 포맷팅
                    if isinstance(price, (int, float)) and price > 0:
                        price_str = f"{int(price):,}원"
                    else:
                        price_str = str(price) if price else "가격미표시"

                    # 방송시간 포맷팅
                    time_str = str(air_time) if air_time else "시간미표시"

                    # 중복 제거 키
                    unique_key = f"{channel}_{time_str}_{title}_{price_str}"
                    if unique_key not in seen_keys:
                        seen_keys.add(unique_key)
                        items.append({
                            "수집일자": today_str,
                            "방송시간": time_str,
                            "품목명": title.strip(),
                            "가격": price_str
                        })

    except Exception as e:
        print(f"API 수집 중 오류 발생: {e}")

    # 만약 백엔드 엔드포인트 응답 형태에 따른 fallback 처리
    if not items:
        print("메인 API 직접 호출 fallback 처리 중 (웹 API 엔드포인트)...")
        fallback_url = "https://trend.hsmoa-ad.com/api/schedule"
        try:
            fb_res = requests.get(fallback_url, params={"date": today_str, "cate": "건강식품"}, headers=headers, timeout=15)
            if fb_res.status_code == 200:
                fb_data = fb_res.json()
                fb_list = fb_data if isinstance(fb_data, list) else fb_data.get("list", [])
                for item in fb_list:
                    title = item.get("title") or item.get("name")
                    price = item.get("price")
                    time_str = item.get("time", "시간미표시")
                    if title:
                        price_str = f"{int(price):,}원" if isinstance(price, (int, float)) else str(price)
                        items.append({
                            "수집일자": today_str,
                            "방송시간": time_str,
                            "품목명": str(title).strip(),
                            "가격": price_str
                        })
        except Exception as fb_e:
            print(f"Fallback 시도 참고: {fb_e}")

    print(f"오늘 당일 수집된 총 건강식품 방송 건수: {len(items)}건")

    if not items:
        print("수집된 데이터가 없습니다.")
        return

    # CSV 저장 (수집일자, 방송시간, 품목명, 가격 4개 셀)
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
