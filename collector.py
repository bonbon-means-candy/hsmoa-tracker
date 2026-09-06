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

        print("1. 홈쇼핑모아 트렌드랩 편성표 접속...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        # 2. '홈쇼핑 전체 편성표' 클릭 및 카테고리 필터 적용
        try:
            # 전체 편성표 클릭
            tab_btn = page.locator("text='홈쇼핑 전체 편성표'").first
            if await tab_btn.is_visible():
                await tab_btn.click()
                await page.wait_for_timeout(1500)

            # 1차 카테고리 [식품] 클릭
            food_btn = page.locator("button, div, span").filter(has_text=re.compile(r"^식품$")).first
            if await food_btn.is_visible():
                await food_btn.click()
                await page.wait_for_timeout(1500)

            # 2차 카테고리 [건강식품] 클릭
            health_btn = page.locator("button, div, span, label").filter(has_text=re.compile(r"^건강식품$")).first
            if await health_btn.is_visible():
                await health_btn.click()
                await page.wait_for_timeout(3000)
                print("2. [식품 > 건강식품] 카테고리 선택 완료")
        except Exception as e:
            print(f"카테고리 선택 처리 참고: {e}")

        # 스크롤 동작으로 동적 데이터 로딩
        for _ in range(8):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(800)

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')

        # 非건강식품 키워드 차단 리스트 (화장품, 가전, 일반식품, 생활용품 등)
        exclude_keywords = [
            # 생활/가전/뷰티
            "샴푸", "청소기", "세제", "트리트먼트", "염색약", "화장품", "앰플", "크림", 
            "마스크팩", "소파", "침대", "매트리스", "원피스", "팬츠", "자켓", "패딩", 
            "에어프라이어", "냄비", "프라이팬", "건조기", "세탁기", "냉장고", "청소",
            # 일반 식품 (농수축산물/가공식품)
            "김치", "갈비", "돈까스", "만두", "탕", "찌개", "고기", "제육", "족발", 
            "보쌈", "순대", "떡볶이", "오징어", "굴비", "전복", "빈대떡", "사과", 
            "배", "귤", "샤인머스캣", "쌀", "포도", "고구마", "감자", "김", "미역"
        ]

        # 3. 데이터 추출
        elements = await page.query_selector_all("main div, div[class*='schedule'], a[href*='product']")

        for elem in elements:
            try:
                text = await elem.inner_text()
                if not text:
                    continue

                if "원" in text and ("오전" in text or "오후" in text or ":" in text):
                    lines = [l.strip() for l in text.split("\n") if l.strip()]

                    if len(lines) >= 2:
                        air_time = ""
                        title = ""
                        price = ""

                        for line in lines:
                            # 방송시간 파싱
                            if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                                if not air_time:
                                    air_time = line
                            # 가격 파싱
                            elif re.search(r'[\d,]+원', line):
                                if not price:
                                    price = line
                            # 품목명 파싱 (홈쇼핑 브랜드명 및 기타 불필요 문구 제외)
                            elif len(line) >= 3 and "원" not in line and not any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑", "무료배송", "적립"]):
                                if not title:
                                    title = line

                        # 비건강식품 키워드 포함 시 스킵
                        if title and price:
                            if any(ex in title for ex in exclude_keywords):
                                continue

                            # 4. 홈쇼핑사 칼럼 제외 (수집일자, 방송시간, 품목명, 가격만 기입)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": air_time if air_time else "시간미표시",
                                "품목명": title,
                                "가격": price
                            })
            except Exception:
                continue

        await browser.close()

        if not items:
            print("수집된 건강기능식품 데이터가 없습니다.")
            return

        # 5. DataFrame 변환 및 중복 제거
        df = pd.DataFrame(items)
        df = df.drop_duplicates(subset=["품목명", "가격"])

        os.makedirs("data/daily", exist_ok=True)
        os.makedirs("data/monthly", exist_ok=True)

        daily_path = f"data/daily/hsmoa_{today_str}.csv"
        month_str = datetime.today().strftime('%Y-%m')
        monthly_path = f"data/monthly/hsmoa_{month_str}.csv"

        df.to_csv(daily_path, index=False, encoding="utf-8-sig")
        print(f"건강식품 일간 수집 완료 ({len(df)}건): {daily_path}")

        if os.path.exists(monthly_path):
            df_old = pd.read_csv(monthly_path)
            df_merged = pd.concat([df_old, df]).drop_duplicates(subset=["수집일자", "품목명", "가격"])
            df_merged.to_csv(monthly_path, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(monthly_path, index=False, encoding="utf-8-sig")

if __name__ == "__main__":
    asyncio.run(collect_hsmoa_schedule())
