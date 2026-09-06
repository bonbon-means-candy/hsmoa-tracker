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

        print("1. 페이지 접속 및 로딩 대기...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        # 2. 카테고리 필터 선택: 식품 > 건강식품
        try:
            # 식품 클릭
            food_element = page.locator("text='식품'").first
            if await food_element.is_visible():
                await food_element.click()
                await page.wait_for_timeout(1500)

            # 건강식품 클릭
            health_element = page.locator("text='건강식품'").first
            if await health_element.is_visible():
                await health_element.click()
                await page.wait_for_timeout(3000)
                print("2. [식품 > 건강식품] 카테고리 선택 완료")
        except Exception as e:
            print(f"카테고리 선택 처리 참고: {e}")

        # 3. 전체 타임라인 로딩을 위한 넓은 범위 스크롤 및 지연
        for _ in range(8):
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(800)

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')

        # 4. 방송 카드 전체 요소 수집 (텍스트 블록 정밀 분석)
        # 홈쇼핑모아의 모든 링크 및 카드 컨테이너 파싱
        elements = await page.query_selector_all("main div, a[href*='product'], div[class*='schedule']")

        for elem in elements:
            try:
                text = await elem.inner_text()
                if not text:
                    continue

                # '원'이 포함되고 최소 2줄 이상인 방송 정보 덩어리 추출
                if "원" in text and ("오전" in text or "오후" in text or ":" in text):
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    
                    if len(lines) >= 3:
                        air_time = ""
                        channel = ""
                        title = ""
                        price = ""

                        for line in lines:
                            # 시간 패턴 (예: 오전 10:20, 14:30)
                            if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                                if not air_time:
                                    air_time = line
                            # 가격 패턴 (예: 129,000원)
                            elif re.search(r'[\d,]+원', line):
                                if not price:
                                    price = line
                            # 채널명 (CJ, GS, 현대, 롯데, NS, 홈앤, 공영 등)
                            elif any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑"]):
                                if not channel:
                                    channel = line
                            # 품목명 (나머지 긴 텍스트)
                            else:
                                if not title and len(line) >= 4 and "원" not in line:
                                    title = line

                        # 유효 데이터인 경우 정제 항목 추가
                        if title and price:
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
            print("수집된 데이터가 없습니다.")
            return

        # 5. DataFrame 변환 및 중복 데이터 제거
        df = pd.DataFrame(items)
        df = df.drop_duplicates(subset=["품목명", "가격"])

        # 엑셀 셀 분리 및 UTF-8 BOM 저장
        os.makedirs("data/daily", exist_ok=True)
        os.makedirs("data/monthly", exist_ok=True)

        daily_path = f"data/daily/hsmoa_{today_str}.csv"
        month_str = datetime.today().strftime('%Y-%m')
        monthly_path = f"data/monthly/hsmoa_{month_str}.csv"

        df.to_csv(daily_path, index=False, encoding="utf-8-sig")
        print(f"일간 수집 완료 ({len(df)}건 저장): {daily_path}")

        if os.path.exists(monthly_path):
            df_old = pd.read_csv(monthly_path)
            df_merged = pd.concat([df_old, df]).drop_duplicates(subset=["수집일자", "품목명", "가격"])
            df_merged.to_csv(monthly_path, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(monthly_path, index=False, encoding="utf-8-sig")

if __name__ == "__main__":
    asyncio.run(collect_hsmoa_schedule())
