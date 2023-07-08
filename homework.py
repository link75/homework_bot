import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

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


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия обязательных переменных окружения (токенов)."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if not value:
            logger.critical('Отсутствует обязательная '
                            f'переменная окружения: {key}. '
                            'Программа принудительно остановлена.')
            sys.exit(1)
    return True


def send_message(bot, message):
    """Отправка сообщения чат-боту."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено в Telegram.')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения в Telegram: {error}.')


def get_api_answer(timestamp):
    """Получение информации от API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

    except Exception as error:
        logger.error(f'Ошибка при запросе к API: {error}.')

    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            f'Ошибка в ответе сервера API! Код ответа: {response.status_code}'
        )

    return response.json()


def check_response(response):
    """Проверка ответа API на валидность данных."""
    if not isinstance(response, dict):
        raise TypeError('В ответе API структура данных '
                        'не соответствует ожиданиям (ожидается словарь).')

    elif 'homeworks' not in response:
        raise KeyError('В ответе API домашней работы нет ключа "homeworks"')

    elif (not isinstance(response['homeworks'], list) or
          not response['homeworks']):
        raise TypeError('В ответе API домашней работы данные приходят '
                        'в другом формате (ожидается непустой список).')

    homework = response['homeworks'][0]
    return homework


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
    logger.info('Проверка токенов пройдена.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    logger.debug(timestamp)
    last_status = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            status = parse_status(homework)
            if status != last_status:
                send_message(bot, message=status)
                last_status = status
            logger.debug('В ответе API нет обновлений по '
                         'статусу домашней работы.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
