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
# SOS_FIELD_SELECT = "//span[text()='SOS Аптека стоит']"
# Используется для отладки, таблица с данными
SOS_FIELD_SELECT = "//span[text()='Сбойные чеки, расхождение в отчетности']"
APPLY_BUTTON = "//div[text()='Применить']/../.."
APPLICATION_NUMBER = "//table[@class='cellTableWidget']/tbody/tr//div[@class='integerView']"
APPLICATION_DATE = "//table[@class='cellTableWidget']/tbody/tr/td[@__did='serviceCall@SolvedDataTime']//div[@class='tableDatetimeAttr']"


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
    options.add_argument('--headless=old')  # Это улучшенная версия headless режима для новых версий Chrome
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--disable-gpu')  # Обязательно отключите GPU для работы headless режима на Windows
    options.add_argument('--no-sandbox')  # Иногда помогает на Windows
    options.add_argument('--disable-dev-shm-usage')  # Устраняет ошибки с использованием shared memory
    options.add_argument('--window-size=1920,1080')
    # options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--enable-logging')
    options.add_argument('--v=1')
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(60)
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
    wait = WebDriverWait(driver, 60)
    applications_tab = wait.until(EC.element_to_be_clickable((By.XPATH, APPLICATIONS_TAB)))
    applications_tab.click()
    logging.info("2) Нажимаем на кнопку 'Заявки'")
    time.sleep(5)


def apply_filters(driver):
    """Применение фильтров."""
    wait = WebDriverWait(driver, 60)
    logging.info("3) Применяем фильтр")

    try:
        logging.debug("3.1) Элемент 'Сбросить' не найден, нажимаем на кнопку фильтрации")
        filter_button = wait.until(EC.element_to_be_clickable((By.XPATH, FILTER_BUTTON)))
        filter_button.click()
        time.sleep(0.5)
    except Exception:
        reset_filter_button = wait.until(EC.presence_of_element_located((By.XPATH, RESET_FILTER)))
        logging.debug("3.2) Найден элемент 'Сбросить', нажимаем на него")
        reset_filter_button.click()
        time.sleep(0.5)

    service_field = wait.until(EC.visibility_of_element_located((By.XPATH, SERVICE_FIELD)))
    service_field.click()
    logging.debug("3.3) Вставляем в первое поле 'Услуга'")
    service_field.send_keys('услуга')
    time.sleep(0.5)
    service_field_select = wait.until(EC.visibility_of_element_located((By.XPATH, SERVICE_FIELD_SELECT)))
    service_field_select.click()
    time.sleep(0.5)

    sos_field = driver.find_element(By.XPATH, SOS_FIELD)
    sos_field.click()
    logging.debug("3.4) Вставляем во второе поле 'SOS Аптека стоит'")
    # sos_field.send_keys('sos аптека стоит')
    sos_field.send_keys('сбойные чеки, рас')  # Используется для отладки, таблица с данными
    time.sleep(1)
    sos_field_select = wait.until(EC.visibility_of_element_located((By.XPATH, SOS_FIELD_SELECT)))
    time.sleep(5)
    sos_field_select.click()
    time.sleep(0.5)
    apply_button = driver.find_element(By.XPATH, APPLY_BUTTON)
    apply_button.click()
    logging.debug("3.5) Нажали на кнопку применить")
    time.sleep(0.5)


def collect_data(driver):
    """Сбор номеров заявок и дат."""
    wait = WebDriverWait(driver, 30)
    logging.info("4) Готовим перечень заявок и их номера")
    data = []
    try:
        time.sleep(2)
        # Проверяем, есть ли номера заявок
        numbers = wait.until(EC.presence_of_all_elements_located((By.XPATH, APPLICATION_NUMBER)))
        dates = wait.until(EC.presence_of_all_elements_located((By.XPATH, APPLICATION_DATE)))

        if numbers and dates:
            logging.debug(f"Полученные номера заявок: {[num.text for num in numbers]}")
            logging.debug(f"Полученные даты регистрации: {[date.text for date in dates]}")

            data = list(zip([num.text for num in numbers], [date.text for date in dates]))

            for num, date in data:
                logging.debug(f"Номер заявки: {num}, Дата регистрации: {date}")

    except TimeoutException:
        logging.info("4.1) Заявки не найдены (TimeoutException).")
    except Exception as e:
        text_e = f"Произошла ошибка при сборе данных: {e}"
        logging.exception(text_e)
        # send_message_to_channel(text_e)
    finally:
        return data


def main():
    """Сердце"""
    processed_applications = set()  # Множество уже отработанных заявок по которым уже было отправлено сообщение
    last_message_time = datetime.now()  # Время последнего отправленного сообщения
    startup_message_sent = False  # Флаг для отслеживания отправки стартового сообщения
    while True:
        driver = None
        try:
            driver = setup_driver()
            login(driver, URL, LOGIN_USERNAME, LOGIN_PASSWORD)
            navigate_to_applications(driver)
            apply_filters(driver)
            data = collect_data(driver)

            if data:
                current_applications = set(num for num, date in data)  # Все заявки текущей итерации
                new_applications = current_applications - processed_applications  # Новые заявки
                if new_applications:
                    message_lines = []
                    for num, date in data:
                        if num in new_applications:
                            message_lines.append(f"Номер: {num}, Дата: {date}")
                    message = "Новые заявки:\n" + "\n".join(message_lines)
                    logging.info("Отправляем сообщение в Telegram:")
                    logging.info(message)
                    send_message_to_channel(message, disable_notification=True)  # Со звуком False
                    processed_applications.update(new_applications)
                    last_message_time = datetime.now()
                else:
                    logging.info("Новых заявок нет.")
            else:
                if not startup_message_sent:
                    startup_message = f"С момента запуска заявок не было {datetime.now().strftime('%Y-%m-%d %H:%M')}."
                    logging.info(f"Отправляем информационное сообщение без звука: {startup_message}")
                    send_message_to_channel(startup_message, disable_notification=True)
                    startup_message_sent = True
            if datetime.now() - last_message_time >= timedelta(hours=1):
                info_message = f"Скрипт работает. Новых заявок нет на {datetime.now().strftime('%Y-%m-%d %H:%M')}."
                logging.info(f"Отправляем информационное сообщение без звука: {info_message}")
                send_message_to_channel(info_message, disable_notification=True)  # Без звука
                last_message_time = datetime.now()
        except Exception as e:
            text_e = f"Произошла ошибка в main: {e}"
            logging.exception(text_e)
            # send_message_to_channel(text_e)
        finally:
            if driver:
                driver.quit()
            logging.info("Ждём 5 минут перед следующей проверкой...")
            time.sleep(300)


if __name__ == "__main__":
    main()
