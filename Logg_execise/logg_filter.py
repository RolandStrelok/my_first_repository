import logging


# Определяем свой фильтр, наследуясь от класса Filter библиотеки logging
class ErrorLogFilter(logging.Filter):
    # Переопределяем метод filter, который принимает 'self' и 'record'
    # Переменная рекорд будет ссылаться на объект класса LogRecord
    def filter(delf, record):
        return record.levelname == 'ERROR' and 'важно' in record.msg.lower()
    

# Иницмализируем логгер
logger = logging.getLogger(__name__)

# Создаем хэндлер, который будет направлять логи в stderr
stderr_handler = logging.StreamHandler()

# Подключаем фильтр к хэндлеру
stderr_handler.addFilter(ErrorLogFilter())

# Подключаем хэндлер к логгеру
logger.addHandler(stderr_handler)

logger.warning('Важно! Это лог с предупреждением!')
logger.error('Важно! Это лог с ошибкой!')
logger.info('Важно! Это лог с уровня INFO!')
logger.error('Это лог с ошибкой!')
