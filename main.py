import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from transformers import GPT2Tokenizer, GPT2LMHeadModel
from io import BytesIO
from docx import Document

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

if not API_TOKEN:
    raise ValueError("API_TOKEN не задан. Проверьте файл .env.")

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
model = GPT2LMHeadModel.from_pretrained('gpt2')


class BotStates(StatesGroup):
    MAIN_MENU = State()
    WAITING_FOR_TEXT = State()


def is_text_generated_by_agi(text):
    tokenizer.pad_token = tokenizer.eos_token
    max_length = 1024
    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=max_length, padding=True)
    attention_mask = inputs["attention_mask"]
    outputs = model.generate(inputs["input_ids"], attention_mask=attention_mask, max_length=max_length,
                             num_return_sequences=1)
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    probability = calculate_similarity(text, generated_text)
    return probability


def calculate_similarity(original, generated):
    return len(set(original.split()) & set(generated.split())) / len(set(original.split()))


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


def extract_text_from_docx(file_content):
    doc = Document(BytesIO(file_content.getvalue()))
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text


@dp.message_handler(text='Вставить текст', state=BotStates.MAIN_MENU)
async def request_text(message: types.Message, state: FSMContext):
    await bot.send_message(chat_id=message.chat.id, text="Пришли текст или файл и я проверю его.", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(BotStates.WAITING_FOR_TEXT)


@dp.message_handler(state=BotStates.WAITING_FOR_TEXT, content_types=[types.ContentType.TEXT, types.ContentType.DOCUMENT])
async def analyze_text(message: types.Message, state: FSMContext):
    logging.info(f"Получено сообщение с типом: {message.content_type}")

    if message.text:
        logging.info(f"Получен текст: {message.text}")
        text = message.text
    elif message.document:
        logging.info(f"Получен документ с именем: {message.document.file_name}")
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        file_content = await bot.download_file(file_path)  # file_content — это объект BytesIO
        logging.info(f"Содержимое файла получено, размер: {len(file_content.getvalue())} байт")

        if message.document.file_name.endswith('.docx'):
            logging.info("Файл .docx, извлекаем текст")
            text = extract_text_from_docx(file_content)
        else:
            logging.info("Не .docx файл, пытаемся декодировать как текст")
            text = file_content.getvalue().decode('utf-8', errors='ignore')

    elif message.forward_from:
        text = message.forward_from.text if message.forward_from.text else "Пересланное сообщение без текста."
        logging.info(f"Пересланное сообщение: {text}")

    analyzing_message = await message.reply("Идет анализ...")

    try:
        logging.info("Начинаем анализ текста")
        probability = is_text_generated_by_agi(text)
        logging.info(f"Анализ завершен, вероятность: {probability * 100:.2f}%")
        await message.reply(f"Вероятность, что текст сгенерирован ИИ: {probability * 100:.2f}%")
    except Exception as e:
        logging.error(f"Ошибка при анализе текста: {e}")
        await message.reply("Произошла ошибка при анализе текста. Пожалуйста, попробуйте позже.")
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=analyzing_message.message_id)

        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        text_btn = KeyboardButton('Вставить текст')
        markup.add(text_btn)

        await message.reply(
            "Что бы вы хотели сделать дальше?",
            reply_markup=markup
        )

        await state.set_state(BotStates.MAIN_MENU)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)