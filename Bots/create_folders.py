from pathlib import Path

# Описание структуры проекта (словарь вложенных пакетов и модулей)
project_structure = {
    'main.py': None,
    'book': {      # Первый уровень: имя пакета
        'book.txt': None
    },
    'config_data': {      # Еще один пакет первого уровня
        'config.py': None
    },
    'database': {      # Еще один пакет первого уровня
        'database.py': None
    },
    'filters': {      # Еще один пакет первого уровня
        'filters.py': None
    },
    'handlers': {      # Еще один пакет первого уровня
        'other_handlers.py': None,
        'user_handlers.py': None,
    },
    'keyboards': {      # Еще один пакет первого уровня
        'bookmarks_kb.py': None,
        'main_menu.py': None,
        'pagination_kb.py': None,
    },
    'lexicon': {      # Еще один пакет первого уровня
        'lexicon.py': None
    },
    'services': {      # Еще один пакет первого уровня
        'file_handling.py': None
    }
}

# Основной путь проекта, нужно прописать адрес
root_folder = 'Абсолютный адрес'

# Функция для рекурсивного создания структуры
def create_package_structure(package_dict, current_path=Path()):
    """
    Рекурсивно создаёт пакеты и модули по заданному дереву.
    :param package_dict: словарь структуры проекта
    :param current_path: текущий путь относительно root_folder
    """
    for key, value in package_dict.items():
        if isinstance(value, dict):  # Если значение — другой пакет (это означает подпакет)
            new_subdir = current_path / key
            new_subdir.mkdir(exist_ok=True)
            create_package_structure(value, new_subdir)  # Продолжаем рекурсию
        else:  # Иначе считаем это именем файла (модуля), создаём пустой файл
            file_path = current_path / key
            file_path.touch()

# Выполняем создание структуры начиная от корня проекта
create_package_structure(project_structure, Path(root_folder))
