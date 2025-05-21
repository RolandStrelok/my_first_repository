from aiogram import Bot, Dispatcher
from aiogram.filters import BaseFilter
from aiogram.types import Message

BOT_TOKEN = '7761378953:AAFhVYvTgv3w7IcNqLk_H7vbJIMPNnpGbs0'

# Создаем объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

#Список с ID администраторов бота
admin_ids: list[int] = [846439894]

#Собственный фильтр, проверяющий юзера на админа
class IsAdmin(BaseFilter):
    def __init__(self, admin_ids: list[int]) -> None:
        #В качестве параметра фильтр принимает список с целыми числами
        self.admin_ids = admin_ids

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in self.admin_ids    


if __name__ == '__main__':
    dp.run_polling(bot)