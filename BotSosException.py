import time
from datetime import datetime, timedelta
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import URL, LOGIN_USERNAME, LOGIN_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

LOGIN_FIELD = "//input[@name='login']"
PASSWORD_FIELD = "//input[@name='password']"
LOGIN_BUTTON = "//button[@type='button']"
APPLICATIONS_TAB = "//a[text()='Заявки']"
DISTRIBUTED_IN_MY_GROUPS_TAB = "//a[text() = 'Распределенные в моих группах']"
SELECT_FILTER = "//span[text() = 'Распределенные заявки на коммандах']/../..//div[@title = 'Настройки списка отличаются от сохраненных в виде']/following-sibling::input"
SELECT_FILTER_ELEMENT_SOS = "//span[text()= 'SOS Аптека']"
APPLY_BUTTON = "//div[text()='Применить']/../.."
APPLICATION_NUMBER = "//table[@class='cellTableWidget']/tbody/tr//div[@class='integerView']"
APPLICATION_SUBJECT = "//table[@class='cellTableWidget']/tbody/tr/td[@__did='serviceCall@shortDescr']//div[@class='stringView']"
OPERATION_ERROR = "//div[text()= 'Операция не может быть выполнена.']"


class OperationCannotBeCompletedException(Exception):
    """Кастомное исключение для всплывающего окна 'Операция не может быть завершена'"""
    pass


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


def check_for_operation_error(driver):
    """Проверка появления окна 'Операция не может быть завершена'"""
    original_implicitly_wait = driver.timeouts.implicit_wait
    try:
        driver.implicitly_wait(0)
        elements = driver.find_elements(By.XPATH, OPERATION_ERROR)
        if elements:
            logging.info("Обнаружено окно: 'Операция не может быть выполнена'")
            raise OperationCannotBeCompletedException("Операция не может быть выполнена.")
    finally:
        driver.implicitly_wait(original_implicitly_wait)


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
    options.add_argument("--incognito")
    options.add_argument('--headless=old')  # Это улучшенная версия headless режима для новых версий Chrome
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--disable-gpu')  # Обязательно отключите GPU для работы headless режима на Windows
    options.add_argument('--no-sandbox')  # Иногда помогает на Windows
    options.add_argument('--disable-dev-shm-usage')  # Устраняет ошибки с использованием shared memory
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(60)
    return driver


def login(driver, url, username, password):
    """Авторизация на сайте."""
    driver.get(url)
    driver.find_element(By.XPATH, LOGIN_FIELD).send_keys(username)
    check_for_operation_error(driver)
    driver.find_element(By.XPATH, PASSWORD_FIELD).send_keys(password)
    check_for_operation_error(driver)
    driver.find_element(By.XPATH, LOGIN_BUTTON).click()
    check_for_operation_error(driver)
    logging.info("1) Авторизация")


def navigate_to_applications(driver):
    """Переход на вкладку заявок."""
    wait = WebDriverWait(driver, 60)
    check_for_operation_error(driver)
    applications_tab = wait.until(EC.element_to_be_clickable((By.XPATH, APPLICATIONS_TAB)))
    check_for_operation_error(driver)
    applications_tab.click()
    check_for_operation_error(driver)
    distributed_in_my_groups = wait.until(EC.element_to_be_clickable((By.XPATH, DISTRIBUTED_IN_MY_GROUPS_TAB)))
    check_for_operation_error(driver)
    distributed_in_my_groups.click()
    check_for_operation_error(driver)
    logging.info("2) Перешли во вкладку 'Распределенные в моих группах'")


def apply_filters(driver):
    """Применение фильтров."""
    wait = WebDriverWait(driver, 60)
    select_filter = wait.until(EC.visibility_of_element_located((By.XPATH, SELECT_FILTER)))
    select_filter.click()
    check_for_operation_error(driver)
    select_filter.send_keys('SOS')
    check_for_operation_error(driver)
    select_filter_element_sos = wait.until(EC.visibility_of_element_located((By.XPATH, SELECT_FILTER_ELEMENT_SOS)))
    select_filter_element_sos.click()
    check_for_operation_error(driver)
    logging.debug("3) Применили фильтр")
    time.sleep(0.5)


def collect_data(driver):
    """Сбор номеров заявок и дат."""
    wait = WebDriverWait(driver, 30)
    logging.info("4) Готовим перечень заявок и их номера")
    data = []
    try:
        time.sleep(2)
        check_for_operation_error(driver)
        # Проверяем, есть ли номера заявок
        numbers = wait.until(EC.presence_of_all_elements_located((By.XPATH, APPLICATION_NUMBER)))
        check_for_operation_error(driver)
        dates = wait.until(EC.presence_of_all_elements_located((By.XPATH, APPLICATION_SUBJECT)))
        check_for_operation_error(driver)

        if numbers and dates:
            logging.debug(f"Полученные номера заявок: {[num.text for num in numbers]}")
            logging.debug(f"Полученные даты регистрации: {[date.text for date in dates]}")

            data = list(zip([num.text for num in numbers], [date.text for date in dates]))

            for num, date in data:
                logging.debug(f"Номер заявки: {num}, Дата регистрации: {date}")

    except TimeoutException:
        logging.info("4.1) Заявки не найдены (TimeoutException).")
    except OperationCannotBeCompletedException:
        raise
    except Exception as e:
        text_e = f"Произошла ошибка при сборе данных: {e}"
        logging.exception(text_e)
        send_message_to_channel(text_e)
    finally:
        return data


def main():
    """Сердце"""
    processed_applications = set()  # Множество уже отработанных заявок по которым уже было отправлено сообщение
    last_message_time = datetime.now()  # Время последнего отправленного сообщения
    startup_message_sent = False  # Флаг для отслеживания отправки стартового сообщения
    while True:
        driver = None
        skip_sleep = False
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
                    send_message_to_channel(message, disable_notification=False)  # Со звуком False
                    processed_applications.update(new_applications)
                    last_message_time = datetime.now()
                else:
                    logging.info("Новых заявок нет.")
            else:
                if not startup_message_sent:
                    startup_message = f"С момента запуска заявок не было {datetime.now().strftime('%Y-%m-%d %H:%M')}."
                    logging.info(f"Отправляем информационное сообщение без звука: {startup_message}")
                    # send_message_to_channel(startup_message, disable_notification=True)
                    startup_message_sent = True
            if datetime.now() - last_message_time >= timedelta(hours=6):
                info_message = f"Скрипт работает. Новых заявок нет на {datetime.now().strftime('%Y-%m-%d %H:%M')}."
                logging.info(f"Отправляем информационное сообщение без звука: {info_message}")
                send_message_to_channel(info_message, disable_notification=True)  # Без звука
                last_message_time = datetime.now()
        except OperationCannotBeCompletedException as e:
            logging.info(f"Обнаружено сообщение: {e}")
            skip_sleep = True
        except Exception as e:
            text_e = f"Произошла ошибка в main: {e}"
            logging.exception(text_e)
            # send_message_to_channel(text_e)
            skip_sleep = True
        finally:
            if driver:
                driver.quit()
            if not skip_sleep:
                logging.info("Ждём 5 минут перед следующей проверкой...")
                time.sleep(300)
            else:
                logging.info("Перезапуск скрипта без ожидания 5 минут из-за ошибки.")


if __name__ == "__main__":
    main()
