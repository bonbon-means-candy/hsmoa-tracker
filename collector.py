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

        # 2. '홈쇼핑 전체 편성표' 탭 클릭
        try:
            all_tab = page.locator("text='홈쇼핑 전체 편성표'").first
            if await all_tab.is_visible():
                await all_tab.click()
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        # 3. 카테고리: [식품] -> [건강식품] 필터 적용
        try:
            food_btn = page.locator("button, div, span").filter(has_text=re.compile(r"^식품$")).first
            if await food_btn.is_visible():
                await food_btn.click()
                await page.wait_for_timeout(1500)

            health_btn = page.locator("button, div, span, label").filter(has_text=re.compile(r"^건강식품$")).first
            if await health_btn.is_visible():
                await health_btn.click()
                await page.wait_for_timeout(3000)
                print("2. [식품 > 건강식품] 카테고리 필터 적용 완료")
        except Exception as e:
            print(f"카테고리 선택 참고: {e}")

        # 4. 당일 편성된 전체 방송 카드가 로딩되도록 바닥까지 무한 스크롤
        print("당일 전체 건강식품 방송 데이터 로딩 중...")
        last_height = await page.evaluate("document.body.scrollHeight")
        
        for _ in range(20):  # 충분한 횟수로 당일 전체 타임라인 로드
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(500)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height and _ > 10:
                break
            last_height = new_height

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')
        seen_keys = set()

        # 5. 당일 편성 카드 추출 및 개별 셀 데이터 파싱
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
                    # 방송 시간 파싱
                    if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                        if not air_time:
                            air_time = line
                    # 가격 파싱
                    elif re.search(r'[\d,]+원', line):
                        if not price:
                            price = line
                    # 품목명 파싱 (홈쇼핑사명 및 무관한 배송/적립 문구 제외)
                    elif len(line) >= 3 and "원" not in line and not any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑", "무료배송", "적립", "방송"]):
                        if not title:
                            title = line

                # 유효 데이터 검증 및 순수 당일 전체 데이터 수집
                if title and price:
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

        print(f"오늘 당일 수집된 총 건강식품 건수: {len(items)}건")

        if not items:
            print("수집된 데이터가 없습니다.")
            return

        # 6. 개별 셀 저장 (수집일자, 방송시간, 품목명, 가격)
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
