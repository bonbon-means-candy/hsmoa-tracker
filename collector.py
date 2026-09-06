import asyncio
import os
import re
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

        # 1. '식품' 클릭 후 '건강식품' 2단계 카테고리 클릭
        try:
            food_btn = page.locator("text=식품").first
            if await food_btn.is_visible():
                await food_btn.click()
                await page.wait_for_timeout(1000)
            
            health_food_btn = page.locator("text=건강식품").first
            if await health_food_btn.is_visible():
                await health_food_btn.click()
                await page.wait_for_timeout(2000)
                print("카테고리: [식품 > 건강식품] 선택 완료")
        except Exception as e:
            print(f"카테고리 선택 참고: {e}")

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')

        # 방송 카드 요소 수집 및 셀별 데이터 구조화
        cards = await page.locator("main div").all()

        for card in cards:
            text = await card.inner_text()
            if text and ("원" in text or "세트" in text or "박스" in text):
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                
                air_time = ""
                channel = ""
                title = ""
                quantity = ""
                price = ""

                for line in lines:
                    if "오전" in line or "오후" in line or (":" in line and len(line) <= 8):
                        air_time = line
                    elif any(c in line for c in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "SK", "KT", "쇼핑"]):
                        channel = line
                    elif "원" in line and any(char.isdigit() for char in line):
                        price = line
                    elif any(q in line for q in ["박스", "병", "포", "개월", "세트", "통", "정"]):
                        quantity = line
                    else:
                        if not title and len(line) > 2:
                            title = line

                if title or price:
                    items.append({
                        "수집일자": today_str,
                        "방송시간": air_time,
                        "홈쇼핑사": channel,
                        "상품명": title if title else " | ".join(lines[:2]),
                        "구성/수량": quantity,
                        "판매가격": price,
                        "전체내용": " | ".join(lines)
                    })

        await browser.close()

        if not items:
            print("수집된 데이터가 없습니다.")
            return

        # 중복 제거 및 데이터프레임 생성
        df_today = pd.DataFrame(items).drop_duplicates(subset=["수집일자", "상품명", "판매가격"])

        # 2. 엑셀에서 깔끔하게 칸별로 열리도록 UTF-8-BOM(utf-8-sig) 저장
        os.makedirs("data/daily", exist_ok=True)
        daily_filename = f"data/daily/hsmoa_{today_str}.csv"
        df_today.to_csv(daily_filename, index=False, encoding="utf-8-sig")
        print(f"일간 데이터 저장 완료: {daily_filename}")

        # 월간 데이터 누적 저장
        month_str = datetime.today().strftime('%Y-%m')
        os.makedirs("data/monthly", exist_ok=True)
        monthly_filename = f"data/monthly/hsmoa_{month_str}.csv"

        if os.path.exists(monthly_filename):
            df_month = pd.read_csv(monthly_filename)
            df_combined = pd.concat([df_month, df_today]).drop_duplicates(subset=["수집일자", "상품명", "판매가격"])
        else:
            df_combined = df_today

        df_combined.to_csv(monthly_filename, index=False, encoding="utf-8-sig")
        print(f"월간 데이터 누적 완료: {monthly_filename}")

if __name__ == "__main__":
    asyncio.run(collect_hsmoa_schedule())
