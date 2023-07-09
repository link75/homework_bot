import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NotForSendingError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия обязательных переменных окружения (токенов)."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if not value:
            logging.critical('Отсутствует обязательная '
                             f'переменная окружения: {key}. '
                             'Программа принудительно остановлена.')
            sys.exit(1)
    return True


def send_message(bot, message):
    """Отправка сообщения чат-боту."""
    try:
        logging.debug('Отправляем сообщение в Telegram.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        message = f'Ошибка отправки сообщения в Telegram: {error}.'
        logging.error(message, exc_info=True)
    else:
        logging.debug('Сообщение отправлено в Telegram.')


def get_api_answer(timestamp):
    """Получение информации от API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        logging.debug('Отправляем запрос к API.')
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

    except Exception as error:
        logging.error(f'Ошибка при запросе к API: {error}.', exc_info=True)

    if response.status_code != HTTPStatus.OK:
        raise requests.exceptions.RequestException(
            f'Ошибка в ответе сервера API! Код ответа: {response.status_code}'
        )

    return response.json()


def check_response(response):
    """Проверка ответа API на валидность данных."""
    if not isinstance(response, dict):
        raise TypeError('В ответе API структура данных '
                        'не соответствует ожиданиям (ожидается словарь dict), '
                        f'а получили другой тип данных: {type(response)}.')

    elif 'homeworks' not in response:
        raise KeyError('В ответе API домашней работы нет ключа "homeworks"')

    elif not isinstance(response['homeworks'], list):
        raise TypeError('В ответе API домашней работы данные приходят '
                        'в другом формате (ожидается непустой список).')


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('В ответе API домашней работы '
                       'нет ключа "homework_name"')

    homework_status = homework.get('status')
    if not homework_status or homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('В ответе API домашней работы '
                       'нет статуса или статус неизвестен.')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    logging.debug('Проверка токенов пройдена.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status = ''
    error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)

            if not response['homeworks']:
                status = last_status
            else:
                status = parse_status(response['homeworks'][0])

            if status != last_status:
                logging.debug('Статус домашней работы изменился.')
                send_message(bot, message=status)
                last_status = status
                timestamp = int(response['current_date'])
            else:
                logging.debug('В ответе API нет обновлений по '
                              'статусу домашней работы.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)

            if message != error_message:
                try:
                    logging.debug('Отправляем сообщение об ошибке в Telegram.')
                    send_message(bot, message)
                    error_message = message
                except NotForSendingError:
                    message = 'Сообщение об ошибке отправить не удалось.'
                    logging.error(message, exc_info=True)
                else:
                    logging.debug('Сообщение об ошибке отправлено в Telegram.')

        finally:
            time.sleep(RETRY_PERIOD)


def logger():
    """Настройки логгера."""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG,
        stream=sys.stdout,
    )


if __name__ == '__main__':
    logger()
    main()
