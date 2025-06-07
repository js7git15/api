import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ChatMemberHandler,
)

# Настройки бота
TOKEN = "ВАШ_ТОКЕН_БОТА"
CHANNEL_ID = -1001234567890  # ID вашего канала (должен начинаться с -100)
ADMIN_ID = 123456789  # ID администратора для уведомлений

# Вопросы для проверки (можно добавить больше)
QUESTIONS = [
    "Напишите ответ на вопрос: сколько будет 2+2?",
    "Напишите слово 'человек' в ответном сообщении",
    "Ответьте на это сообщение любым осмысленным текстом",
]

# Хранилище данных (в реальном проекте лучше использовать БД)
pending_users = {}
user_attempts = {}

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    update.message.reply_text(f"Привет, {user.first_name}! Я бот для проверки заявок в канал.")

def check_chat_join(update: Update, context: CallbackContext) -> None:
    """Обработчик событий вступления в канал"""
    chat_member = update.chat_member
    if chat_member.chat.id == CHANNEL_ID:
        user = chat_member.new_chat_member.user
        # Проверяем, что это новый участник (статус changed from left/restricted)
        if chat_member.old_chat_member.status in ['left', 'restricted'] and chat_member.new_chat_member.status == 'restricted':
            # Отправляем сообщение с проверкой
            send_verification_message(user, context)

def send_verification_message(user, context: CallbackContext):
    """Отправляет сообщение с проверкой пользователю"""
    try:
        # Выбираем случайный вопрос
        question = context.bot_data.get('questions', QUESTIONS)[0]
        
        # Сохраняем информацию о проверке
        pending_users[user.id] = {
            'question': question,
            'attempts': 0
        }
        
        # Отправляем сообщение с вопросом
        context.bot.send_message(
            chat_id=user.id,
            text=f"Для вступления в канал необходимо подтвердить, что вы не бот.\n\n{question}\n\nУ вас есть 3 попытки.",
        )
        
        # Уведомляем администратора
        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Новый пользователь {user.full_name} (@{user.username}) ожидает проверки. Отправлен вопрос: {question}",
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user.id}: {e}")
        # Если не удалось отправить сообщение, отклоняем заявку
        context.bot.decline_chat_join_request(CHANNEL_ID, user.id)

def handle_message(update: Update, context: CallbackContext) -> None:
    """Обработчик ответов пользователя"""
    user = update.effective_user
    message = update.message
    
    if user.id in pending_users:
        verification_data = pending_users[user.id]
        question = verification_data['question']
        attempts = verification_data['attempts']
        correct = False
        
        # Проверяем ответ (простая проверка, можно усложнить)
        if "2+2" in question and "4" in message.text:
            correct = True
        elif "человек" in question and "человек" in message.text.lower():
            correct = True
        elif "осмысленным текстом" in question and len(message.text.split()) > 2:
            correct = True
        
        if correct:
            # Одобряем заявку
            try:
                context.bot.approve_chat_join_request(CHANNEL_ID, user.id)
                message.reply_text("Спасибо! Ваша заявка одобрена. Добро пожаловать в канал!")
                del pending_users[user.id]
                
                # Уведомляем администратора
                context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"Пользователь {user.full_name} (@{user.username}) успешно прошел проверку.",
                )
            except Exception as e:
                logger.error(f"Ошибка при одобрении заявки: {e}")
                message.reply_text("Произошла ошибка. Пожалуйста, попробуйте позже.")
        else:
            # Неправильный ответ
            attempts += 1
            pending_users[user.id]['attempts'] = attempts
            
            if attempts >= 3:
                # Превышено количество попыток - отклоняем заявку
                try:
                    context.bot.decline_chat_join_request(CHANNEL_ID, user.id)
                    message.reply_text("Превышено количество попыток. Ваша заявка отклонена.")
                    del pending_users[user.id]
                    
                    # Уведомляем администратора
                    context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"Пользователь {user.full_name} (@{user.username}) не прошел проверку после 3 попыток.",
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отклонении заявки: {e}")
                    message.reply_text("Произошла ошибка. Пожалуйста, попробуйте позже.")
            else:
                message.reply_text(f"Неправильный ответ. У вас осталось {3 - attempts} попыток.")

def error_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик ошибок"""
    logger.error(msg="Ошибка в боте:", exc_info=context.error)
    
    if update and update.effective_user:
        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Произошла ошибка в боте при обработке сообщения от {update.effective_user.full_name}",
        )

def main() -> None:
    """Запуск бота"""
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Обработчики команд
    dispatcher.add_handler(CommandHandler("start", start))
    
    # Обработчик вступлений в канал
    dispatcher.add_handler(ChatMemberHandler(check_chat_join))
    
    # Обработчик текстовых сообщений
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Обработчик ошибок
    dispatcher.add_error_handler(error_handler)

    # Запуск бота
    updater.start_polling()
    logger.info("Бот запущен и работает...")
    updater.idle()

if __name__ == '__main__':
    main()