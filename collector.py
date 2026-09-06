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

        print("1. 편성표 페이지 접속...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        # 2. '홈쇼핑 전체 편성표' 탭 확실히 클릭
        try:
            all_tab = page.locator("text='홈쇼핑 전체 편성표'").first
            if await all_tab.is_visible():
                await all_tab.click()
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        # 3. 카테고리: [식품] -> [건강식품] 정확히 클릭
        try:
            # 식품 클릭
            food_btn = page.locator("button, div, span").filter(has_text=re.compile(r"^식품$")).first
            if await food_btn.is_visible():
                await food_btn.click()
                await page.wait_for_timeout(1500)

            # 건강식품 클릭
            health_btn = page.locator("button, div, span, label").filter(has_text=re.compile(r"^건강식품$")).first
            if await health_btn.is_visible():
                await health_btn.click()
                await page.wait_for_timeout(3000)
                print("2. [식품 > 건강식품] 필터 선택 완료")
        except Exception as e:
            print(f"카테고리 선택 참고: {e}")

        # 4. 70건의 방송 카드가 모두 DOM에 로드되도록 충분히 스크롤 (타임라인 로딩)
        print("전체 70건 방송 데이터 로딩 중...")
        for _ in range(15):
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(600)

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')

        # 5. 건강식품 편성표 카드 영역만 '정확한 컨테이너'로 추출
        # 전체 div 스캔 대신, 실제로 가격("원")과 시간 정보가 같이 들어있는 방송 카드 단위 추출
        cards = await page.query_selector_all("div[class*='item'], div[class*='card'], div[class*='schedule'], a[href*='product']")

        seen_keys = set()

        for card in cards:
            try:
                # 카드 내부 텍스트 추출
                text = await card.inner_text()
                if not text or "원" not in text:
                    continue

                lines = [l.strip() for l in text.split("\n") if l.strip()]

                # 방송시간, 상품명, 가격 파싱
                air_time = ""
                title = ""
                price = ""

                for line in lines:
                    # 방송 시간 (예: 10:20~11:30, 오전 09:10, 14:00)
                    if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                        if not air_time:
                            air_time = line
                    # 가격 (예: 159,000원)
                    elif re.search(r'[\d,]+원', line):
                        if not price:
                            price = line
                    # 상품명 (방송사 브랜드명, 배송 관련 문구 제외)
                    elif len(line) >= 4 and "원" not in line and not any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑", "무료배송", "적립", "방송"]):
                        if not title:
                            title = line

                # 유효 데이터 검증 (상품명과 가격이 존재하고, 중복이 아닌 경우)
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

        print(f"총 수집된 건수: {len(items)}건")

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
