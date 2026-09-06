import asyncio
import os
import re
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

async def collect_hsmoa_schedule():
    async with async_playwright() as p:
        # 브라우저 실행
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("1. 홈쇼핑모아 트렌드랩 접속...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 2. 홈쇼핑 전체 편성표 탭 클릭
        try:
            tab_btn = page.locator("text='홈쇼핑 전체 편성표'").first
            if await tab_btn.is_visible():
                await tab_btn.click()
                await page.wait_for_timeout(1500)
                print("2. '홈쇼핑 전체 편성표' 탭 클릭 완료")
        except Exception as e:
            print(f"편성표 탭 클릭 참고: {e}")

        # 3. 카테고리 : 식품 -> 2차 카테고리 : 건강식품 클릭
        try:
            # 1차 카테고리 '식품' 클릭
            food_btn = page.locator("button:has-text('식품'), div:has-text('식품')").filter(has_text=re.compile(r"^식품$")).first
            if await food_btn.is_visible():
                await food_btn.click()
                await page.wait_for_timeout(1500)
            else:
                # 텍스트로 재시도
                await page.click("text=식품")
                await page.wait_for_timeout(1500)

            # 2차 카테고리 '건강식품' 클릭
            health_btn = page.locator("button:has-text('건강식품'), div:has-text('건강식품')").filter(has_text=re.compile(r"^건강식품$")).first
            if await health_btn.is_visible():
                await health_btn.click()
                await page.wait_for_timeout(2500)
                print("3. 카테고리 [식품 > 건강식품] 클릭 완료")
            else:
                await page.click("text=건강식품")
                await page.wait_for_timeout(2500)
                print("3. 카테고리 [건강식품] 클릭 완료")
        except Exception as e:
            print(f"카테고리 선택 참고: {e}")

        # 편성표 항목 로딩을 위한 스크롤 다운 (데이터 확보)
        print("편성표 데이터 로딩 중 (스크롤)...")
        for _ in range(5):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(1000)

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')

        # 4. 모든 방영물 카드 추출 (각 방송 단위 아이템 선택)
        # 홈쇼핑모아 카드 컨테이너 파싱
        cards = await page.query_selector_all("a, div[class*='card'], div[class*='item']")

        for card in cards:
            text = await card.inner_text()
            if not text:
                continue

            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # 방송 항목 조건 확인 ("원" 가격 정보가 포함된 영역만 추출)
            if len(lines) >= 2 and any('원' in line for line in lines):
                air_time = ""
                title = ""
                price = ""

                for line in lines:
                    # 방송시간 파싱 (예: 10:20, 22:30, 오전 08:10 등)
                    if re.search(r'\d{1,2}:\d{2}', line) or '오전' in line or '오후' in line:
                        if not air_time:
                            air_time = line
                    # 가격 파싱 (예: 89,000원, 109,000원)
                    elif re.search(r'[\d,]+원', line):
                        if not price:
                            price = line
                    # 품목명 (시간, 가격, 홈쇼핑 브랜드명 제외한 상품 이름)
                    elif len(line) > 3 and not any(brand in line for brand in ["CJ온스타일", "GS샵", "현대홈쇼핑", "롯데홈쇼핑", "NS홈쇼핑", "홈앤쇼핑", "공영쇼핑", "신세계쇼핑", "KT알파"]):
                        if not title:
                            title = line

                # 품목명과 가격이 추출된 유효한 항목만 정제
                if title and price:
                    items.append({
                        "수집일자": today_str,
                        "방송시간": air_time if air_time else "시간미표시",
                        "품목명": title,
                        "가격": price
                    })

        await browser.close()

        if not items:
            print("수집된 방영물 데이터가 없습니다.")
            return

        # 5. 수집 파일 개별 셀 저장 (중복 제거 및 칼럼 정렬)
        df = pd.DataFrame(items)
        df = df.drop_duplicates(subset=["품목명", "가격"])

        # 저장 디렉토리 설정
        os.makedirs("data/daily", exist_ok=True)
        os.makedirs("data/monthly", exist_ok=True)

        daily_path = f"data/daily/hsmoa_{today_str}.csv"
        month_str = datetime.today().strftime('%Y-%m')
        monthly_path = f"data/monthly/hsmoa_{month_str}.csv"

        # 엑셀에서 개별 셀로 깔끔히 열리도록 utf-8-sig 적용
        df.to_csv(daily_path, index=False, encoding="utf-8-sig")
        print(f"일간 데이터 저장 완료 ({len(df)}건): {daily_path}")

        if os.path.exists(monthly_path):
            df_old = pd.read_csv(monthly_path)
            df_merged = pd.concat([df_old, df]).drop_duplicates(subset=["수집일자", "품목명", "가격"])
            df_merged.to_csv(monthly_path, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(monthly_path, index=False, encoding="utf-8-sig")

        print(f"월간 데이터 누적 저장 완료: {monthly_path}")

if __name__ == "__main__":
    asyncio.run(collect_hsmoa_schedule())
