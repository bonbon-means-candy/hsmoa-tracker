import asyncio
import os
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

async def collect_hsmoa_schedule():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("홈쇼핑모아 트렌드랩 접속 중...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")

        try:
            category_btn = page.locator("text=건강식품")
            if await category_btn.count() > 0:
                await category_btn.first.click()
                await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"카테고리 선택 참고: {e}")

        items = []
        cards = await page.locator("main div").all()
        today_str = datetime.today().strftime('%Y-%m-%d')

        for card in cards:
            text = await card.inner_text()
            if text and ("원" in text or "세트" in text or "박스" in text):
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                items.append({
                    "date": today_str,
                    "raw_content": " | ".join(lines)
                })

        await browser.close()

        if not items:
            print("수집된 데이터가 없습니다.")
            return

        # 일간 CSV 저장
        df_today = pd.DataFrame(items).drop_duplicates()
        os.makedirs("data/daily", exist_ok=True)
        daily_filename = f"data/daily/hsmoa_{today_str}.csv"
        df_today.to_csv(daily_filename, index=False, encoding="utf-8-sig")

        # 월간 CSV 누적 저장
        month_str = datetime.today().strftime('%Y-%m')
        os.makedirs("data/monthly", exist_ok=True)
        monthly_filename = f"data/monthly/hsmoa_{month_str}.csv"

        if os.path.exists(monthly_filename):
            df_month = pd.read_csv(monthly_filename)
            df_combined = pd.concat([df_month, df_today]).drop_duplicates()
        else:
            df_combined = df_today

        df_combined.to_csv(monthly_filename, index=False, encoding="utf-8-sig")
        print("수집 완료!")

if __name__ == "__main__":
    asyncio.run(collect_hsmoa_schedule())
