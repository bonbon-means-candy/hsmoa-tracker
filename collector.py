import asyncio
import os
import re
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

async def collect_hsmoa_schedule():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("1. 홈쇼핑모아 편성표 접속...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        # 2. 카테고리 필터 [식품] -> [건강식품] 클릭 및 네트워크 대기
        try:
            category_btns = page.locator("button, div, a, span, label")
            
            # '식품' 클릭
            food_elem = category_btns.filter(has_text=re.compile(r"^식품$")).first
            if await food_elem.is_visible():
                await food_elem.click()
                await page.wait_for_timeout(1500)

            # '건강식품' 클릭
            health_elem = category_btns.filter(has_text=re.compile(r"^건강식품$")).first
            if await health_elem.is_visible():
                await health_elem.click()
                await page.wait_for_timeout(3000)
                print("2. [식품 > 건강식품] 카테고리 선택 시도 완료")
        except Exception as e:
            print(f"필터 클릭 참고: {e}")

        # 3. 타임라인 전체 스크롤 (동적 카드 로딩)
        print("방송 데이터 스크롤 로딩 중...")
        for _ in range(15):
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(600)

        # 4. 건강식품/건강기능식품 키워드 정의 (화이트리스트)
        health_keywords = [
            "유산균", "콜라겐", "비타민", "루테인", "홍삼", "아르기닌", "다이어트", "효소", 
            "콘드로이친", "오메가", "밀크씨슬", "프로틴", "단백질", "글루타치온", "칼슘", 
            "마그네슘", "MSM", "관절", "혈당", "크릴오일", "프로폴리스", "보스웰리아", 
            "침향", "경옥고", "에스더", "정관장", "여에스더", "종근당", "대웅", "CJ웰케어",
            "건강", "진액", "즙", "매스티드", "카무트", "바나바", "모로오렌지", "아스타잔틴",
            "유기농", "새싹보리", "ABC주스", "석류", "타트체리", "락토페린", "프리바이오틱스",
            "프로바이오틱스", "세라티드", "면역", "피부", "소화", "눈건강", "간건강"
        ]

        # 절대 포함되면 안 되는 일반식품 및 타 카테고리 키워드 (블랙리스트)
        exclude_keywords = [
            "김치", "포기", "총각", "열무", "갈비", "돈까스", "만두", "탕", "찌개", "고기", 
            "족발", "빈대떡", "사과", "쌀", "굴비", "전복", "오징어", "떡", "과일", "샤인머스캣",
            "샴푸", "청소기", "세제", "화장품", "앰플", "크림", "소파", "침대", "원피스", "팬츠"
        ]

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')
        seen_keys = set()

        # 5. 방송 카드 데이터 정밀 추출
        cards = await page.query_selector_all("div[class*='item'], div[class*='card'], div[class*='schedule'], a[href*='product']")

        for card in cards:
            try:
                text = await card.inner_text()
                if not text or "원" not in text:
                    continue

                lines = [l.strip() for l in text.split("\n") if l.strip()]

                air_time = ""
                title = ""
                price = ""

                for line in lines:
                    if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                        if not air_time:
                            air_time = line
                    elif re.search(r'[\d,]+원', line):
                        if not price:
                            price = line
                    elif len(line) >= 3 and "원" not in line and not any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑", "무료배송", "적립", "방송"]):
                        if not title:
                            title = line

                if title and price:
                    # [검증 1] 일반식품(김치, 고기 등) 및 잡화 블랙리스트 제외
                    if any(ex in title for ex in exclude_keywords):
                        continue

                    # [검증 2] 건강식품 키워드가 포함되어 있거나 명확한 건강 관련 상품인 경우만 수집
                    is_health = any(kw in title for kw in health_keywords)
                    
                    # 키워드 검증을 통과했거나 일반 음식/잡화가 아닌 경우
                    if is_health:
                        unique_key = f"{air_time}_{title}_{price}"
                        if unique_key not in seen_keys:
                            seen_keys.add(unique_key)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": air_time if air_time else "시간미표시",
                                "품목명": title,
                                "가격": price
                            })
            except Exception:
                continue

        await browser.close()

        print(f"오늘 당일 수집된 정밀 건강식품 건수: {len(items)}건")

        if not items:
            print("수집된 데이터가 없습니다.")
            return

        # 6. 저장 (수집일자, 방송시간, 품목명, 가격 4개 셀)
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
    asyncio.run(collect_hsmoa_schedule())
