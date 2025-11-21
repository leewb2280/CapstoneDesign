import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

# [설정 및 유틸리티 불러오기]
# config.py: URL, 저장 파일명 등 변경될 수 있는 설정값
# utils.py: 브라우저 실행, 가격 숫자 변환, 스크롤 등 반복되는 기능 함수
from config import OLIVEYOUNG_URL, SCRAPED_DATA_PATH
from utils import setup_chrome_driver, clean_price_text, scroll_to_bottom


def main():
    # 1. 브라우저 드라이버 설정 및 실행
    # (OS를 감지하여 적절한 옵션으로 크롬을 켭니다 - utils.py 참조)
    driver = setup_chrome_driver()
    if not driver:
        return

    try:
        # 2. 올리브영 랭킹 페이지 접속
        print(f"🌐 접속 중: {OLIVEYOUNG_URL}")
        driver.get(OLIVEYOUNG_URL)

        # [중요] 사이트 보안(Cloudflare) 및 로딩을 위해 랜덤 시간 대기
        time.sleep(random.uniform(5, 8))

        # 3. 팝업창 닫기 (팝업이 떴을 경우에만 처리)
        try:
            close_btn = driver.find_element(By.CLASS_NAME, 'pop_close_btn')
            close_btn.click()
            print("✅ 팝업 닫기 완료")
            time.sleep(1)
        except:
            # 팝업이 없으면 에러 무시하고 계속 진행
            pass

        # 4. 페이지 스크롤 (더 많은 상품 로딩)
        # utils.py에 있는 함수를 사용해 화면을 5번 내립니다.
        scroll_to_bottom(driver, count=5)

        # 5. HTML 파싱 (BeautifulSoup)
        # 현재 브라우저에 로딩된 페이지 소스를 가져와서 분석하기 쉽게 변환
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        data_list = []

        # 상품 리스트 컨테이너 찾기 (CSS 선택자 사용)
        product_containers = soup.select('ul.list_goods > li')
        # 혹시 뷰 모드가 달라서 태그가 다를 경우를 대비한 예비 선택자
        if not product_containers:
            product_containers = soup.select('ul.prd_list > li')

        print(f"📦 상품 {len(product_containers)}개 발견.")

        # 6. 개별 상품 정보 추출 반복문
        for container in product_containers:
            try:
                # 상품명 추출
                name_tag = container.select_one('.prd_name .tx_name')
                if not name_tag: continue  # 이름이 없으면 데이터로서 가치가 없으므로 건너뜀

                name = name_tag.text.strip()

                # 가격 추출 (utils의 clean_price_text 함수로 쉼표 제거 및 정수 변환)
                final_tag = container.select_one('.tx_cur') # 할인가(최종가)
                org_tag = container.select_one('.tx_org')   # 정가(원가)

                final_price = clean_price_text(final_tag.text) if final_tag else 0
                org_price = clean_price_text(org_tag.text) if org_tag else final_price

                # 할인율 계산 (정가가 0이 아니고, 실제 할인이 있을 때만 계산)
                discount = 0.0
                if org_price > 0 and final_price < org_price:
                    discount = round(((org_price - final_price) / org_price) * 100, 1)

                # 상품 ID 및 상세 페이지 링크 추출
                link_tag = container.select_one('a[data-ref-goodsno]')
                pid = link_tag['data-ref-goodsno'] if link_tag else "N/A"
                link = link_tag['href'] if link_tag else ""

                # 추출한 정보를 리스트에 딕셔너리 형태로 추가
                data_list.append({
                    'ID': pid,
                    '상품명': name,
                    '원가': org_price,
                    '최종가': final_price,
                    '할인율': discount,
                    'URL': link
                })
            except Exception as e:
                # 특정 상품 하나에서 에러가 나도 멈추지 않고 다음 상품으로 넘어감
                continue

        # 7. 데이터 저장 (CSV)
        if data_list:
            df = pd.DataFrame(data_list)
            # utf-8-sig: 엑셀에서 한글 깨짐 방지
            df.to_csv(SCRAPED_DATA_PATH, index=False, encoding='utf-8-sig')
            print(f"💾 저장 완료: {SCRAPED_DATA_PATH} ({len(df)}개)")
        else:
            print("⚠️ 저장할 데이터가 없습니다.")

    except Exception as e:
        print(f"⚠️ 전체 실행 중 오류 발생: {e}")

    finally:
        # [필수] 에러 발생 여부와 상관없이 브라우저는 반드시 종료
        driver.quit()
        print("👋 종료")


if __name__ == "__main__":
    main()