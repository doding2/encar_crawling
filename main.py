import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.ie.webdriver import WebDriver
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import time
import re


CHROME_DRIVER_PATH = 'C:\\Users\\drago\\PycharmProjects\\encar_crawling\\chromedriver\\chromedriver.exe'

NUM_DRIVERS = 3
driver_pool = Queue()


def create_driver() -> WebDriver:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 브라우저 창을 띄우지 않음
    driver = webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=options)
    return driver


def init_driver_pool():
    for _ in range(NUM_DRIVERS):
        driver_pool.put(create_driver())


def get_detail_link_list() -> [str]:
    driver = driver_pool.get()
    url = 'https://car.encar.com/list/car?page=1&search=%7B%22type%22%3A%22car%22%2C%22action%22%3A%22(And.Hidden.N._.CarType.A.)%22%2C%22title%22%3A%22%EA%B5%AD%EC%82%B0%C2%B7%EC%88%98%EC%9E%85%22%2C%22toggle%22%3A%7B%7D%2C%22layer%22%3A%22%22%2C%22sort%22%3A%22MobileModifiedDate%22%7D'
    driver.get(url)
    time.sleep(3)

    car_list_box = driver.find_elements(By.XPATH, '//*[@id="__next"]/div[1]/div[4]/div[3]/div')
    link_list = []

    for car_box in car_list_box:
        try:
            link = car_box.find_element(By.TAG_NAME, "a").get_attribute('href')
            if link and "encar.com/cars/detail/" in link:
                link_list.append(link)
        except:
            pass

    driver_pool.put(driver)  # 작업이 끝난 드라이버를 다시 풀에 반환

    return link_list


def get_detail_data(link: str):
    driver = driver_pool.get()
    driver.get(link)
    time.sleep(2)

    car = {'링크': link}

    try:
        # parse title
        title_box = driver.find_element(By.XPATH, '//*[@id="wrap"]/div/div[1]/div[1]/div[4]/div[1]/h3')
        title = " ".join([t.text for t in title_box.find_elements(By.TAG_NAME, "span")])
        car['이름'] = title

        # open detail sheet
        detail_button = driver.find_element(By.XPATH, '//*[@id="wrap"]/div/div[1]/div[1]/div[4]/div[1]/div/button')
        detail_button.click()
        time.sleep(1)

        # parse detail data
        detail_sheet = driver.find_elements(By.XPATH, '//*[@id="bottom_sheet"]/div[2]/div[2]/div/ul/li')
        for element in detail_sheet:
            key_string = element.find_element(By.TAG_NAME, "strong").text
            key = clean_detail_key_text(key_string)
            value = element.find_elements(By.TAG_NAME, "span")[-1].text
            if '자세히보기' in value:
                outer_value = element.find_element(By.TAG_NAME, 'span').text
                inner_value = element.find_element(By.CSS_SELECTOR, 'span > span').text
                value = outer_value[:-len(inner_value)]
            car[key] = value

        # open views detail dialog
        try:
            # num of detail dialog list is 12
            views_detail_button = driver.find_element(By.XPATH, '//*[@id="bottom_sheet"]/div[2]/div[2]/div/ul/li[12]/strong/span/button')
        except Exception as e:
            # num of detail dialog list is 13
            views_detail_button = driver.find_element(By.XPATH, '//*[@id="bottom_sheet"]/div[2]/div[2]/div/ul/li[13]/strong/span/button')
        views_detail_button.click()
        time.sleep(1)

        # parse post date
        post_date_box = driver.find_element(By.XPATH, '/html/body/div[6]/div/span[1]/div')
        post_date = clean_post_date_text(post_date_box.text)
        car['최초등록일'] = post_date

        print(f"✅ {car}")
    except Exception as e:
        print(f"❌ Error fetching data from {link}: {e}")

    driver_pool.put(driver)  # 작업이 끝난 드라이버를 다시 풀에 반환

    return car


def clean_detail_key_text(text: str) -> str:
    pattern = r"^(.*?)\1 자세히보기$"  # 앞 단어(.*?)가 두 번 반복되고 "자세히보기"가 붙는 경우
    match = re.match(pattern, text)
    return match.group(1) if match else text  # 패턴이 맞으면 첫 번째 그룹 반환, 아니면 원본 반환


def clean_post_date_text(text: str) -> str:
    # '조회수는 10분 간격으로 반영됩니다.' 제거
    text = text.replace("조회수는 10분 간격으로 반영됩니다.", "").strip()
    # '최초등록일 YYYY/MM/DD' 패턴 추출
    match = re.search(r"최초등록일 (\d{4}/\d{2}/\d{2})", text)
    return match.group(1) if match else ""


def main():
    init_driver_pool()
    print('driver pool 초기화')

    link_list = get_detail_link_list()
    print(f'자세한 중고차 link list 가져오기: {len(link_list)}개')

    with ThreadPoolExecutor(max_workers=NUM_DRIVERS) as executor:  # n개 스레드 동시 실행
        executor.map(get_detail_data, link_list)

    # 모든 작업이 끝나면 드라이버 종료
    while not driver_pool.empty():
        driver = driver_pool.get()
        driver.quit()
    print('작업 종료')


if __name__ == '__main__':
    main()