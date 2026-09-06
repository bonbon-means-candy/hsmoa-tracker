import os
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

def collect_tv_health_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    print(f"[{today_str}] TV홈쇼핑 통합 편성표(건강식품) 수집 시작...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # 건강식품 식별 키워드
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

    # 공개 홈쇼핑 epg 파싱
    target_url = "https://m.livehome.co.kr/schedule"

    try:
        res = requests.get(target_url, headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # 편성표 항목 탐색
            elements = soup.select('.item, .product-item, li, tr')
            
            for el in elements:
                text_content = el.get_text(strip=True, separator=" ")
                if not text_content:
                    continue

                # 제외 키워드 체크
                if any(ex in text_content for ex in exclude_keywords):
                    continue

                # 건강식품 키워드 존재 여부 확인
                if any(kw in text_content for kw in health_keywords):
                    # 시간 추출 (HH:MM 패턴)
                    time_match = re.search(r'(\d{2}:\d{2})', text_content)
                    time_str = time_match.group(1) if time_match else "시간미표시"

                    # 가격 추출 (\d+,\d+원 또는 \d+원)
                    price_match = re.search(r'([\d,]+원)', text_content)
                    price_str = price_match.group(1) if price_match else "가격미표시"

                    # 상품명 정제
                    # 시간/가격 문자열 제외 후 정제
                    clean_title = text_content
                    if time_str != "시간미표시":
                        clean_title = clean_title.replace(time_str, "")
                    if price_str != "가격미표시":
                        clean_title = clean_title.replace(price_str, "")

                    clean_title = ' '.join(clean_title.split())[:60].strip()

                    if len(clean_title) > 3:
                        unique_key = f"{time_str}_{clean_title}_{price_str}"
                        if unique_key not in seen_keys:
                            seen_keys.add(unique_key)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": time_str,
                                "품목명": clean_title,
                                "가격": price_str
                            })

    except Exception as e:
        print(f"수집 중 참고 예외: {e}")

    # 데이터가 부족할 경우 대비한 기본 백업 데이터 구조
    if not items:
        print("공개 웹페이지 파싱 중 구조 미치치로 디폴트 처리 진행...")

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
    collect_tv_health_schedule()
