import time
from datetime import datetime, timedelta
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import URL, LOGIN_USERNAME, LOGIN_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

LOGIN_FIELD = "//input[@name='login']"
PASSWORD_FIELD = "//input[@name='password']"
LOGIN_BUTTON = "//button[@type='button']"
APPLICATIONS_TAB = "//a[text()='Заявки']"
RESET_FILTER = "//a[text()= 'Сбросить']"
FILTER_BUTTON = "//div[@title='Фильтрация...']"
SERVICE_FIELD = "(//div[@class='wide-content']//input[@class='formselect'])[1]"
SERVICE_FIELD_SELECT = "//span[text()='Услуга']"
SOS_FIELD = "(//div[@class='wide-content']//input[@class='formselect'])[2]"
SOS_FIELD_SELECT = "//span[text()='SOS Аптека стоит']"
# Используется для отладки, таблица с данными
# SOS_FIELD_SELECT = "//span[text()='Сбойные чеки, расхождение в отчетности']"
APPLY_BUTTON = "//div[text()='Применить']/../.."
APPLICATION_NUMBER = "//table[@class='cellTableWidget']/tbody/tr//div[@class='integerView']"
APPLICATION_DATE = "//table[@class='cellTableWidget']/tbody/tr/td[@__did='abstractBO@lastModifiedDate']//div[" \
                   "@class='tableDatetimeAttr'] "


def send_message_to_channel(message, disable_notification=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHANNEL_ID,
        'text': message,
        'disable_notification': disable_notification
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        logging.info("Сообщение успешно отправлено в канал.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Не удалось отправить сообщение: {e}")


def setup_driver():
    """Настроить драйвер Chrome."""
    options = Options()
    options.add_experimental_option('prefs', {
        'profile.password_manager_enabled': False,
        'credentials_enable_service': False,
    })
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_argument('--disable-autofill')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-infobars')
    # options.add_argument("--incognito")
    # options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver


def login(driver, url, username, password):
    """Авторизация на сайте."""
    driver.get(url)
    driver.find_element(By.XPATH, LOGIN_FIELD).send_keys(username)
    driver.find_element(By.XPATH, PASSWORD_FIELD).send_keys(password)
    driver.find_element(By.XPATH, LOGIN_BUTTON).click()
    logging.info("1) Проходим авторизацию")
    time.sleep(10)


def navigate_to_applications(driver):
    """Переход на вкладку заявок."""
    wait = WebDriverWait(driver, 30)
    applications_tab = wait.until(EC.element_to_be_clickable((By.XPATH, APPLICATIONS_TAB)))
    applications_tab.click()
    logging.info("2) Нажимаем на кнопку 'Заявки'")
    time.sleep(5)


def apply_filters(driver):
    """Применение фильтров."""
    wait = WebDriverWait(driver, 30)

    try:
        reset_filter_button = wait.until(EC.presence_of_element_located((By.XPATH, RESET_FILTER)))
        logging.info("3.1) Найден элемент 'Сбросить', нажимаем на него")
        reset_filter_button.click()
        time.sleep(0.5)
    except Exception:
        logging.info("3.2) Элемент 'Сбросить' не найден, нажимаем на кнопку фильтрации")
        filter_button = wait.until(EC.element_to_be_clickable((By.XPATH, FILTER_BUTTON)))
        filter_button.click()
        time.sleep(0.5)

    service_field = wait.until(EC.visibility_of_element_located((By.XPATH, SERVICE_FIELD)))
    service_field.click()
    logging.info("4) Вставляем в первое поле 'Услуга'")
    service_field.send_keys('услуга')
    time.sleep(0.5)
    service_field_select = wait.until(EC.visibility_of_element_located((By.XPATH, SERVICE_FIELD_SELECT)))
    service_field_select.click()
    time.sleep(0.5)

    sos_field = driver.find_element(By.XPATH, SOS_FIELD)
    sos_field.click()
    logging.info("5) Вставляем во второе поле 'SOS Аптека стоит'")
    sos_field.send_keys('sos аптека стоит')
    # sos_field.send_keys('сбойные чеки, рас')  # Используется для отладки, таблица с данными
    time.sleep(1)
    sos_field_select = wait.until(EC.visibility_of_element_located((By.XPATH, SOS_FIELD_SELECT)))
    time.sleep(5)
    sos_field_select.click()
    logging.info("5.1) Выбрали элемент во втором поле")
    time.sleep(0.5)
    apply_button = driver.find_element(By.XPATH, APPLY_BUTTON)
    apply_button.click()
    logging.info("5.2) Нажали на кнопку применить")
    time.sleep(0.5)


def collect_data(driver):
    """Сбор номеров заявок и дат."""
    wait = WebDriverWait(driver, 30)
    logging.info("6) Готовим перечень заявок и их номера")
    data = []
    try:
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.XPATH, "//table[@class='cellTableWidget']")))
        # Проверяем, есть ли номера заявок
        numbers = driver.find_elements(By.XPATH, APPLICATION_NUMBER)
        dates = driver.find_elements(By.XPATH, APPLICATION_DATE)

        if numbers and dates:
            logging.info(f"Полученные номера заявок: {[num.text for num in numbers]}")
            logging.info(f"Полученные даты регистрации: {[date.text for date in dates]}")

            data = list(zip([num.text for num in numbers], [date.text for date in dates]))

            for num, date in data:
                logging.info(f"Номер заявки: {num}, Дата регистрации: {date}")
        else:
            logging.info("Нет заявок на данный момент.")
    except TimeoutException:
        logging.info("Нет заявок на данный момент (TimeoutException).")
    except Exception as e:
        logging.exception("Произошла ошибка при сборе данных.")
        send_message_to_channel(f"Произошла ошибка при сборе данных: {e}")
    finally:
        return data


def main():
    """Сердце"""
    processed_applications = set()
    last_message_time = datetime.now()
    while True:
        driver = None
        try:
            driver = setup_driver()
            login(driver, URL, LOGIN_USERNAME, LOGIN_PASSWORD)
            navigate_to_applications(driver)
            apply_filters(driver)
            data = collect_data(driver)
            if data:
                current_applications = set(num for num, date in data)
                new_applications = current_applications - processed_applications
                if new_applications:
                    message_lines = []
                    for num, date in data:
                        if num in new_applications:
                            message_lines.append(f"Номер: {num}, Дата: {date}")
                    message = "Новые заявки:\n" + "\n".join(message_lines)
                    logging.info("Отправляем сообщение в Telegram:")
                    logging.info(message)
                    send_message_to_channel(message, disable_notification=False)  # Со звуком
                    processed_applications.update(new_applications)
                    last_message_time = datetime.now()
                else:
                    logging.info("Новых заявок нет.")
            else:
                logging.info("Нет данных о заявках.")
            if datetime.now() - last_message_time >= timedelta(hours=1):
                info_message = f"Скрипт работает. Новых заявок нет на {datetime.now().strftime('%Y-%m-%d %H:%M')}."
                logging.info("Отправляем информационное сообщение без звука.")
                send_message_to_channel(info_message, disable_notification=True)  # Без звука
                last_message_time = datetime.now()
        except Exception as e:
            logging.exception("Произошла ошибка в main.")
            send_message_to_channel(f"Произошла ошибка в main: {e}")
        finally:
            if driver:
                driver.quit()
            logging.info("Ждём 5 минут перед следующей проверкой...")
            time.sleep(300)


if __name__ == "__main__":
    main()
