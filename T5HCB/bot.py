_from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import datetime
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import logging
import os
import sys
from quart import Quart, render_template_string
import asyncio
import threading

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Время запуска бота
START_TIME = datetime.datetime.now()

# Создаем Quart приложение
app = Quart(__name__)

# Список всех пользователей бота
users = set()

# ID администраторов
ADMINS = {1328776237, 5764625744}  # Глава и Зам

# Текущий выбор пользователя (чтобы запомнить, кому отправлять)
user_choices = {}

def get_uptime():
    """Получить время работы бота"""
    current_time = datetime.datetime.now()
    uptime = current_time - START_TIME
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    seconds = uptime.seconds % 60
    return f"{days}д {hours}ч {minutes}м {seconds}с"

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статус бота и время работы (доступно всем)"""
    uptime = get_uptime()
    status_message = (
        f"✅ Бот работает\n"
        f"⏱ Время работы: {uptime}\n"
        f"📊 Пользователей: {len(users)}"
    )
    
    # Добавляем дополнительную информацию для админов
    if is_admin(update.effective_user.id):
        status_message += f"\n\n🔧 Режим администратора"
    
    await update.message.reply_text(status_message)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMINS

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезапуск бота (только для админов)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды")
        return
    
    await update.message.reply_text("🔄 Перезапуск бота...")
    logger.info("Инициирован перезапуск бота администратором")
    
    # Завершаем текущий процесс и перезапускаем
    os.execv(sys.executable, ['python'] + sys.argv)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправка сообщения всем пользователям (только для админов)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды")
        return
    
    message_text = ' '.join(context.args)
    if not message_text:
        await update.message.reply_text("❗️ Укажите текст сообщения после команды /broadcast")
        return
    
    success_count = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
    
    await update.message.reply_text(f"✅ Сообщение отправлено {success_count} пользователям")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и инструкция с кнопками"""
    users.add(update.effective_user.id)
    bot_info = await context.bot.get_me()
    
    keyboard = [
        [InlineKeyboardButton("📝 Отправить сообщение", callback_data="menu_send")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")],
        [InlineKeyboardButton("📊 Статус бота", callback_data="menu_status")]
    ]
    
    # Добавляем кнопки администрирования для админов
    if is_admin(update.effective_user.id):
        keyboard.append([
            InlineKeyboardButton("🛠 Админ-панель", callback_data="menu_admin")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет! Я {bot_info.first_name}, бот для анонимных сообщений.\n\n"
        "🔒 Я помогу тебе отправить анонимное сообщение одному из получателей.\n"
        "📱 Используй кнопки ниже для навигации:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать справку"""
    help_text = (
        "📖 Доступные команды:\n\n"
        "/start - Запустить бота\n"
        "/send - Отправить анонимное сообщение\n"
        "/help - Показать эту справку\n"
        "/status - Показать статус бота\n"
        "/developer_info - Информация о разработчике\n"
        "/privacy - Политика конфиденциальности\n\n"
        "❗️ Как отправить анонимное сообщение:\n"
        "1️⃣ Используйте /send или кнопку 'Отправить сообщение'\n"
        "2️⃣ Выберите получателя\n"
        "3️⃣ Напишите сообщение\n\n"
        "✅ Ваше сообщение будет доставлено анонимно"
    )
    
    # Добавляем информацию для админов
    if is_admin(update.effective_user.id):
        help_text += (
            "\n\n🔧 Команды администратора:\n"
            "/broadcast - Отправить сообщение всем пользователям\n"
            "/restart - Перезапустить бота"
        )
    
    keyboard = [
        [InlineKeyboardButton("📝 Отправить сообщение", callback_data="menu_send")],
        [InlineKeyboardButton("📊 Статус бота", callback_data="menu_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка кнопок меню"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_send":
        keyboard = [
            [InlineKeyboardButton("👤 Глава", callback_data="target_1")],
            [InlineKeyboardButton("👤 Заместитель", callback_data="target_2")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📩 Выберите получателя сообщения:",
            reply_markup=reply_markup
        )
    elif query.data == "menu_help":
        await help_command(update, context)
    elif query.data == "menu_status":
        await status(update, context)
    elif query.data == "menu_admin":
        if is_admin(query.from_user.id):
            keyboard = [
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
                [InlineKeyboardButton("🔄 Restart", callback_data="admin_restart")],
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🛠 Админ-панель:\n\n"
                "Выберите действие:",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("⛔️ У вас нет доступа к админ-панели")
    elif query.data == "menu_main":
        await start(update, context)
    elif query.data == "admin_stats":
        if is_admin(query.from_user.id):
            uptime = get_uptime()
            await query.edit_message_text(
                f"📊 Статистика бота:\n\n"
                f"⏱ Время работы: {uptime}\n"
                f"👥 Пользователей: {len(users)}\n"
                f"🆔 Ваш ID: {query.from_user.id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="menu_admin")]
                ])
            )

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбор получателя через кнопки"""
    keyboard = [
        [InlineKeyboardButton("Глава", callback_data="target_1")],
        [InlineKeyboardButton("Заместитель", callback_data="target_2")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("❓ Кому отправить сообщение?", reply_markup=reply_markup)

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора получателя"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "target_1":
        user_choices[user_id] = 1328776237  # ID главы
        await query.edit_message_text("✅ Выбран Глава. Теперь напиши сообщение:")
    elif query.data == "target_2":
        user_choices[user_id] = 5764625744  # ID заместителя
        await query.edit_message_text("✅ Выбран Заместитель. Теперь напиши сообщение:")
    elif query.data == "admin_restart":
        if is_admin(query.from_user.id):
            await query.edit_message_text("🔄 Подготовка к перезапуску...")
            await restart(update, context)
    elif query.data == "admin_broadcast":
        if is_admin(query.from_user.id):
            await query.edit_message_text(
                "📢 Введите сообщение для рассылки всем пользователям:\n\n"
                "Используйте команду /broadcast <текст сообщения>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="menu_admin")]
                ])
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправка анонимного сообщения выбранному получателю"""
    user_id = update.effective_user.id
    reply_to = update.message.reply_to_message

    if reply_to and "Анонимное сообщение" in reply_to.text:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"↩️ Ответ на ваше анонимное сообщение:\n\n{update.message.text}",
                reply_to_message_id=reply_to.message_id
            )
            await update.message.reply_text("✅ Ответ отправлен!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка при отправке ответа!")
        return

    if user_id not in user_choices:
        await update.message.reply_text("❌ Сначала выбери получателя через /send")
        return

    target_id = user_choices[user_id]
    message_text = update.message.text

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"📨 Анонимное сообщение:\n\n{message_text}\n\n↩️ Чтобы ответить, ответьте на это сообщение"
        )
        await update.message.reply_text("✅ Сообщение отправлено анонимно!")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка! Возможно, получатель заблокировал бота.")

    del user_choices[user_id]

async def developer_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать информацию о разработчике"""
    await update.message.reply_text(
        "ℹ️ Информация о разработчике:\n\n"
        "👨‍💻 Разработчик: @GeorgijSoldativ\n"
        "📧 Email: нету\n"
        "🌐 GitHub: лень загружать\n\n"
    )

async def privacy_policy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать политику конфиденциальности"""
    privacy_text = (
        "📜 Политика конфиденциальности\n\n"
        "Ваши данные и конфиденциальность важны для нас. Мы не собираем "
        "персональные данные пользователей без их согласия.\n\n"
        "1. **Сбор информации:** Мы собираем только те данные, которые "
        "необходимы для работы бота, такие как ID пользователей для "
        "отправки анонимных сообщений.\n\n"
        "2. **Использование данных:** Данные используются исключительно "
        "для обработки запросов пользователей и отправки сообщений.\n\n"
        "3. **Безопасность:** Мы предпринимаем все необходимое, чтобы "
        "защитить ваши данные от несанкционированного доступа.\n\n"
        "4. **Изменения в политике:** Мы можем изменять эту политику "
        "в любое время. Пожалуйста, периодически проверяйте ее на наличие "
        "обновлений.\n\n"
        "Если у вас есть вопросы, пожалуйста, свяжитесь с разработчиком."
    )
    
    await update.message.reply_text(privacy_text)

@app.route('/')
async def home():
    uptime = get_uptime()
    return await render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Telegram Bot</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    background-color: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #2c3e50;
                }
                .status {
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Бот работает!</h1>
                <p>Используйте Telegram для взаимодействия с ботом.</p>
                
                <div class="status">
                    <h3>Статус бота:</h3>
                    <p><strong>Время работы:</strong> {{ uptime }}</p>
                    <p><strong>Пользователей:</strong> {{ users_count }}</p>
                </div>
                
                <p>Ссылка на бота: <a href="https://t.me/{{ bot_name }}" target="_blank">@{{ bot_name }}</a></p>
            </div>
        </body>
        </html>
    """, uptime=uptime, users_count=len(users), bot_name="your_bot_username")

@app.route('/ping')
async def ping():
    return "pong"

async def run_bot():
    """Запуск Telegram бота"""
    application = Application.builder().token("7687849847:AAGTa_uuZNUyimY9lGyJncxlBSuXSMduLfo").build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("send", send))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("developer_info", developer_info))
    application.add_handler(CommandHandler("privacy", privacy_policy))
    application.add_handler(CommandHandler("restart", restart))

    # Обработчики кнопок и сообщений
    application.add_handler(CallbackQueryHandler(handle_menu, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(handle_choice, pattern="^(target_|admin_)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск бота
    print("Запуск Telegram бота...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

async def main():
    """Основная функция для запуска бота и веб-сервера"""
    # Запускаем бота в отдельной асинхронной задаче
    bot_task = asyncio.create_task(run_bot())
    
    # Запускаем веб-сервер
    web_task = asyncio.create_task(app.run_task(host='0.0.0.0', port=8080))
    
    # Ожидаем завершения обеих задач
    await asyncio.gather(bot_task, web_task)

if __name__ == '__main__':
    # Настройка для работы в Replit
    from threading import Thread
    
    # Запускаем бота в отдельном потоке
    Thread(target=lambda: asyncio.run(run_bot())).start()
    
    # Запускаем веб-сервер в основном потоке
    app.run(host='0.0.0.0', port=8080)