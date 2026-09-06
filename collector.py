import asyncio
import json
import os
import re
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

async def collect_hsmoa_schedule():
    captured_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 백엔드 API 응답(JSON)을 가로채는 이벤트 리스너 설정
        async def handle_response(response):
            # 편성표/상품 목록을 반환하는 API 엔드포인트 수신
            if "api" in response.url or "schedule" in response.url or "product" in response.url:
                if response.status == 200:
                    try:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            data = await response.json()
                            captured_data.append(data)
                    except Exception:
                        pass

        page.on("response", handle_response)

        print("1. trend.hsmoa 접속 및 네트워크 API 수신 준비...")
        await page.goto("https://trend.hsmoa-ad.com/schedule", timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 2. 카테고리 [식품] -> [건강식품] 선택하여 해당 API 호출 유도
        try:
            category_btns = page.locator("button, div, a, span, label")
            food_elem = category_btns.filter(has_text=re.compile(r"^식품$")).first
            if await food_elem.is_visible():
                await food_elem.click()
                await page.wait_for_timeout(1000)

            health_elem = category_btns.filter(has_text=re.compile(r"^건강식품$")).first
            if await health_elem.is_visible():
                await health_elem.click()
                await page.wait_for_timeout(2000)
                print("2. [식품 > 건강식품] 카테고리 API 요청 완료")
        except Exception as e:
            print(f"카테고리 클릭 참고: {e}")

        # 3. 전체 데이터 패치 유도를 위해 페이지 트리거
        for _ in range(5):
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(500)

        items = []
        today_str = datetime.today().strftime('%Y-%m-%d')
        seen_keys = set()

        # 4. 가로챈 JSON 데이터에서 순수 방송 항목 재귀적 추출
        def parse_json_items(obj):
            if isinstance(obj, dict):
                # 상품 객체 패턴 탐색 (상품명/가격/시간 키값 매핑)
                title = obj.get("title") or obj.get("name") or obj.get("product_name") or obj.get("goods_name")
                price = obj.get("price") or obj.get("goods_price") or obj.get("discount_price")
                air_time = obj.get("air_time") or obj.get("broadcast_time") or obj.get("start_time") or obj.get("time")

                if title and price:
                    title_str = str(title).strip()
                    price_str = f"{int(price):,}원" if isinstance(price, (int, float)) else str(price)
                    time_str = str(air_time) if air_time else "시간미표시"

                    # 유효성 검증 (배송/이벤트 문구 제외)
                    if len(title_str) >= 3 and not any(b in title_str for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계"]):
                        key = f"{time_str}_{title_str}_{price_str}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": time_str,
                                "품목명": title_str,
                                "가격": price_str
                            })

                for v in obj.values():
                    parse_json_items(v)

            elif isinstance(obj, list):
                for item in obj:
                    parse_json_items(item)

        for json_res in captured_data:
            parse_json_items(json_res)

        # 5. 백엔드 가로채기로 부족할 경우 DOM 백업 보완
        if len(items) < 20:
            print("DOM 카드 파싱으로 추가 보완 수집 진행...")
            cards = await page.query_selector_all("div[class*='item'], div[class*='card'], div[class*='schedule'], a[href*='product']")
            for card in cards:
                try:
                    text = await card.inner_text()
                    if not text or "원" not in text:
                        continue
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    air_time, title, price = "", "", ""
                    for line in lines:
                        if re.search(r'\d{1,2}:\d{2}', line) or "오전" in line or "오후" in line:
                            if not air_time: air_time = line
                        elif re.search(r'[\d,]+원', line):
                            if not price: price = line
                        elif len(line) >= 3 and "원" not in line and not any(b in line for b in ["CJ", "GS", "현대", "롯데", "NS", "홈앤", "공영", "신세계", "KT", "SK", "쇼핑", "무료배송"]):
                            if not title: title = line

                    if title and price:
                        key = f"{air_time}_{title}_{price}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append({
                                "수집일자": today_str,
                                "방송시간": air_time if air_time else "시간미표시",
                                "품목명": title,
                                "가격": price
                            })
                except Exception:
                    continue

        await browser.close()

        print(f"오늘 최종 수집된 건강식품 건수: {len(items)}건")

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
