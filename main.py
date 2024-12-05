from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

if not API_TOKEN:
    raise ValueError("API_TOKEN не задан. Проверьте файл .env.")


storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)


class BotStates(StatesGroup):
    WAITING_FOR_TEXT = State()



@dp.message_handler(commands=['start'], state='*')
async def send_welcome(message: types.Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    text_btn = KeyboardButton('Вставить текст')
    markup.add( text_btn)

    await bot.send_message(
        chat_id=message.chat.id,
        text="Привет, я помогу проверить текст. Выбери опцию.",
        reply_markup=markup
    )
    await state.set_state(BotStates.MAIN_MENU)



@dp.message_handler(text='Вставить текст', state=BotStates.MAIN_MENU)
async def request_text(message: types.Message, state: FSMContext):
    await bot.send_message(chat_id=message.chat.id, text="Пришли текст или файл и я проверю его.", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(BotStates.WAITING_FOR_TEXT)




if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)