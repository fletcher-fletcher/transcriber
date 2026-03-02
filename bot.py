import os
import logging
import asyncio
from pathlib import Path
import whisper
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

ffmpeg_path = r"C:\Users\anton\Downloads\dobro_loader\dobro_loader\bin\ffmpeg.exe"
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
TOKEN = "8625019953:AAFjbYaI0sNkwSw5-OuAvLnhoOz3czaC9Iw"  # Замените на токен вашего бота
ALLOWED_USERS = []  # Если хотите ограничить список пользователей, добавьте их ID

# Загружаем модель Whisper при старте
# Варианты: "tiny", "base", "small", "medium", "large"
# Чем больше модель, тем точнее распознавание, но медленнее и требовательнее к ресурсам
print("Загружаем модель Whisper...")
model = whisper.load_model("base")
print("Модель загружена!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот-расшифровщик голосовых сообщений.\n"
        "Просто перешли мне любое голосовое сообщение, и я пришлю его текст.\n\n"
        "Доступные команды:\n"
        "/help - помощь\n"
        "/model - информация о текущей модели"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет справку"""
    await update.message.reply_text(
        "🎤 Как пользоваться ботом:\n\n"
        "1. Перешлите мне голосовое сообщение из любого чата\n"
        "   или отправьте своё голосовое\n"
        "2. Я скачаю его и обработаю моделью Whisper\n"
        "3. Через несколько секунд вы получите текст\n\n"
        "⚠️ Примечания:\n"
        "- Длинные сообщения (> 2-3 минут) могут обрабатываться дольше\n"
        "- Качество распознавания зависит от качества записи\n"
        "- Поддерживаются многие языки, включая русский и английский"
    )

async def model_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о текущей модели"""
    model_name = "base"  # Текущая модель
    await update.message.reply_text(
        f"🤖 Текущая модель: **{model_name}**\n"
        f"Язык: автоопределение\n"
        f"Точность: средняя (базовая модель)\n\n"
        f"Доступные модели: tiny, base, small, medium, large",
        parse_mode="Markdown"
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает голосовые сообщения"""
    user = update.effective_user
    
    # Проверка доступа (если задан список разрешенных)
    if ALLOWED_USERS and user.id not in ALLOWED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return
    
    # Отправляем статус "печатает", чтобы пользователь знал, что мы работаем
    await update.message.chat.send_action(action="typing")
    
    # Получаем файл голосового сообщения
    voice_file = await update.message.voice.get_file()
    
    # Создаем временный файл
    temp_dir = Path("temp_audio")
    temp_dir.mkdir(exist_ok=True)
    
    # Уникальное имя файла (используем ID сообщения)
    file_path = temp_dir / f"voice_{update.message.message_id}.ogg"
    
    try:
        # Скачиваем файл
        await voice_file.download_to_drive(file_path)
        
        # Отправляем сообщение о начале обработки
        status_msg = await update.message.reply_text(
            "🎧 Получил голосовое. Начинаю распознавание...\n"
            "Это может занять несколько секунд."
        )
        
        # Запускаем распознавание в отдельном потоке, чтобы не блокировать бота
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: model.transcribe(str(file_path), language=None)  # language=None для автоопределения
        )
        
        text = result["text"].strip()
        
        if text:
            # Успешное распознавание
            await status_msg.delete()  # Удаляем сообщение о статусе
            
            # Отправляем результат
            response = f"📝 **Расшифровка:**\n\n{text}"
            
            # Если текст слишком длинный, разбиваем на части
            if len(response) <= 4096:
                await update.message.reply_text(response, parse_mode="Markdown")
            else:
                # Разбиваем на части по 4000 символов
                for i in range(0, len(text), 4000):
                    part = text[i:i+4000]
                    await update.message.reply_text(
                        f"📝 **Часть {i//4000 + 1}:**\n\n{part}",
                        parse_mode="Markdown"
                    )
        else:
            await update.message.reply_text("😕 Не удалось распознать речь. Попробуйте другое сообщение.")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке.\n"
            "Попробуйте ещё раз или отправьте другое сообщение."
        )
    finally:
        # Удаляем временный файл
        if file_path.exists():
            file_path.unlink()

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает аудиофайлы (не голосовые, а файлы .mp3 и т.д.)"""
    await update.message.reply_text(
        "Я пока умею работать только с голосовыми сообщениями 🎤\n"
        "Нажмите на значок микрофона, чтобы записать голосовое, "
        "или перешлите мне голосовое из другого чата."
    )

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("model", model_info))
    
    # Обработчик голосовых сообщений
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Обработчик аудиофайлов (для подсказки)
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    
    # Запускаем бота
    print("Бот запущен! Нажмите Ctrl+C для остановки.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()