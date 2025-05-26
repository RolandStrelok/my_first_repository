import os

from environs import Env


env = Env()  # Создаем экземпляр класса Env
env.read_env()  # Методом read_env() читаем файл .env и загружаем из него переменные в окружение 
                          
bot_token = env('BOT_TOKEN')  # Получаем и сохраняем значение переменной окружения в переменную bot_token
admin_id = env.int('ADMIN_ID')  # Получаем и преобразуем значение переменной окружения к типу int, 
                                # затем сохраняем в переменной admin_id

# Выводим значения переменных в терминал
print(bot_token)
print(admin_id)
print()

# Убедимся также, что переменные есть в окружении
print(os.getenv('BOT_TOKEN'))
print(os.getenv('ADMIN_ID'))
