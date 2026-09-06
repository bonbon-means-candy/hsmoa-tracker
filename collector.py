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

        # 2. 카테고리 필터 정밀 클릭 (식품 -> 건강식품)
        try:
            # '식품' 버튼 클릭
            food_btn = page.locator("div, button, span").filter(has_text=re.compile(r"^식품$")).first
            if await food_btn.is_visible():
                await food_btn.click()
                await page.wait_for_timeout(1500)
                print("1차 카테고리 [식품] 클릭 완료")

            # 하위 '건강식품' 버튼 클릭
            health_btn = page.locator("div, button, span, label").filter(has_text=re.compile(r"^건강식품$")).first
            if await health_btn.is_visible():
                await health_btn.click()
                await page.wait_for_timeout(3000)
                print("2차 카테고리 [건강식품] 필터 적용 완료")
            else:
                # 텍스트 세부 검색으로 재시도
                await page.click("text=건강식품")
                await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"카테고리 필터 적용 참고: {e}")

        # 편성표 타임라인 전체 로딩 (스크롤)
        for _ in range(8):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(800)

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')

        # 제외할 일반 식품 키워드 목록 (안전 필터)
        exclude_keywords = [
            "김치", "갈비", "돈까스", "만두", "탕", "찌개", "고기", "제육", 
            "족발", "보쌈", "순대", "떡볶이", "오징어", "굴비", "전복", "빈대떡",
            "사과", "배", "귤", "샤인머스캣", "쌀", "포도", "고구마", "감자"
        ]

        # 3. 방영물 요소 파싱
        elements = await page.query_selector_all("main div, div[class*='schedule'], a[href*='product']")

        for elem in elements:
            try:
                text = await elem.inner_text()
                if not text:
                    continue

                if "원" in text and ("오전" in text or "오후" in text or ":" in text):
                    lines = [l.strip() for l in text.split("\n") if l.strip()]

                    if len(lines) >= 3:
                        air_time = ""
                        channel = ""
                        title = ""
                        price = ""

                        for line in lines:
                            if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                                if not air_time:
                                    air_time = line
                            elif re.search(r'[\d,]+원', line):
                                if not price:
                                    price = line
                            elif any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑"]):
                                if not channel:
                                    channel = line
                            else:
                                if not title and len(line) >= 3 and "원" not in line:
                                    title = line

                        # 일반 식품 키워드가 들어간 상품은 정제 단계에서 제거
                        if title and price:
                            if any(ex in title for ex in exclude_keywords):
                                continue

                            items.append({
                                "수집일자": today_str,
                                "방송시간": air_time if air_time else "시간미표시",
                                "홈쇼핑사": channel if channel else "전채널",
                                "품목명": title,
                                "가격": price
                            })
            except Exception:
                continue

        await browser.close()

        if not items:
            print("수집된 건강기능식품 데이터가 없습니다.")
            return

        # 4. 개별 셀 저장 및 중복 제거
        df = pd.DataFrame(items)
        df = df.drop_duplicates(subset=["품목명", "가격"])

        os.makedirs("data/daily", exist_ok=True)
        os.makedirs("data/monthly", exist_ok=True)

        daily_path = f"data/daily/hsmoa_{today_str}.csv"
        month_str = datetime.today().strftime('%Y-%m')
        monthly_path = f"data/monthly/hsmoa_{month_str}.csv"

        df.to_csv(daily_path, index=False, encoding="utf-8-sig")
        print(f"건강기능식품 일간 수집 완료 ({len(df)}건): {daily_path}")

        if os.path.exists(monthly_path):
            df_old = pd.read_csv(monthly_path)
            df_merged = pd.concat([df_old, df]).drop_duplicates(subset=["수집일자", "품목명", "가격"])
            df_merged.to_csv(monthly_path, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(monthly_path, index=False, encoding="utf-8-sig")

if __name__ == "__main__":
    asyncio.run(collect_hsmoa_schedule())
