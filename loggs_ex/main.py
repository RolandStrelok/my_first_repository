import logging.config
import os

import yaml
from module_1 import main

current_dir = os.path.dirname(os.path.abspath(__file__))
yaml_file_path = os.path.join(current_dir, 'logging_config.yaml')

with open(yaml_file_path, 'rt') as f:
    config = yaml.safe_load(f.read())
    
# Загружаем настройки логирования из словаря `logging_config`
logging.config.dictConfig(config)

# Исполняем функцию `main` из модуля `module_1.py`
main()