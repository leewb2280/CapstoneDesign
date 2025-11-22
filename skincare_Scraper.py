# skincare_Scraper.py
"""
[올리브영 랭킹 데이터 수집 및 가공 담당]
이 파일은 올리브영 웹사이트의 랭킹 페이지를 크롤링하여 상품 정보를 수집하는 역할을 합니다.

1. 환경 설정 로드 및 Selenium 웹 드라이버 실행 (config.py, utils.py 활용)
2. 올리브영 랭킹 페이지 접속 후 팝업 닫기 및 스크롤 다운(동적 로딩 처리)
3. BeautifulSoup을 활용해 HTML 구조 파싱 및 상품별 데이터 추출
4. 추출된 정보(상품명, 가격, 할인율 등)를 Pandas DataFrame으로 변환하여 CSV 저장
"""

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

        # [수정된 코드 시작] ==========================================
        # 5. HTML 파싱 (BeautifulSoup)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        data_list = []

        # 💡 기존 방식(ul 클래스 찾기) 대신, 상품 이름(.tx_name)이 있는 곳을 먼저 찾습니다.
        # 이렇게 하면 상위 태그(ul) 이름이 바뀌어도 문제없이 찾을 수 있습니다.
        name_tags = soup.select('.tx_name')

        print(f"📦 발견된 상품 이름 태그: {len(name_tags)}개")

        # 상품 이름 태그를 하나씩 돌면서 전체 정보를 추출합니다.
        for name_tag in name_tags:
            try:
                # 1. 상품 컨테이너(li) 찾기: 이름 태그의 부모(li)를 찾습니다.
                container = name_tag.find_parent('li')
                if not container: continue

                # 2. 상품명 추출
                name = name_tag.text.strip()

                # 3. 가격 추출
                final_tag = container.select_one('.tx_cur')  # 할인가(최종가)
                org_tag = container.select_one('.tx_org')  # 정가(원가)

                final_price = clean_price_text(final_tag.text) if final_tag else 0
                # 정가가 없으면 할인가를 정가로 취급
                org_price = clean_price_text(org_tag.text) if org_tag else final_price

                # 4. 할인율 계산
                discount = 0.0
                if org_price > 0 and final_price < org_price:
                    discount = round(((org_price - final_price) / org_price) * 100, 1)

                # 5. 상품 ID 및 링크 추출
                link_tag = container.select_one('a')
                pid = "N/A"
                link = ""

                if link_tag:
                    link = link_tag.get('href', "")
                    # data-ref-goodsno 속성이 있으면 가져오고, 없으면 URL에서 추출 시도
                    if link_tag.has_attr('data-ref-goodsno'):
                        pid = link_tag['data-ref-goodsno']

                # 리스트에 추가
                data_list.append({
                    'ID': pid,
                    '상품명': name,
                    '원가': org_price,
                    '최종가': final_price,
                    '할인율': discount,
                    'URL': link
                })

            except Exception as e:
                print(f"⚠️ 상품 파싱 중 에러: {e}")
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