import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import calendar
import datetime
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# List of allowed user IDs (set through environment variable)
ALLOWED_USERS = set(map(int, os.getenv('ALLOWED_USERS', '').split(',')))

# Database path (set through environment variable or default to /data/weekends.db)
DB_PATH = os.getenv('DB_PATH', '/data/weekends.db')
# Ensure directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Initialize SQLite database
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS weekends (
        user_id INTEGER,
        date TEXT,
        PRIMARY KEY(user_id, date)
    )
    '''
)
conn.commit()

async def send_menu(chat_id, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton('📅 Календарь', callback_data='calendar')],
        [InlineKeyboardButton('🔍 Посмотреть выходные', callback_data='view_weekends')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text='Выберите действие:', reply_markup=reply_markup)

async def start_or_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    if user.id not in ALLOWED_USERS:
        await context.bot.send_message(chat_id=chat_id, text='❌ Доступ запрещен.')
        return
    context.user_data.setdefault('selected_dates', set())
    await send_menu(chat_id, context)

async def calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ALLOWED_USERS:
        await query.edit_message_text('❌ Доступ запрещен.')
        return

    today = datetime.date.today()
    year, month = today.year, today.month
    cal = calendar.monthcalendar(year, month)

    keyboard = []
    weekdays = ['Mo','Tu','We','Th','Fr','Sa','Su']
    keyboard.append([InlineKeyboardButton(d, callback_data='ignore') for d in weekdays])

    selected = context.user_data.get('selected_dates', set())
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(' ', callback_data='ignore'))
            else:
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                label = f"✅{day}" if date_str in selected else str(day)
                row.append(InlineKeyboardButton(label, callback_data=f'date_{date_str}'))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton('💾 Сохранить', callback_data='save_dates')])

    await query.edit_message_text(text='Выберите выходные:', reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data.startswith('date_'):
        date_str = data.split('_',1)[1]
        sel = context.user_data.setdefault('selected_dates', set())
        sel.symmetric_difference_update({date_str})
        await calendar_callback(update, context)

    elif data == 'save_dates':
        sel = context.user_data.get('selected_dates', set())
        cursor.execute('DELETE FROM weekends WHERE user_id = ?', (user_id,))
        cursor.executemany(
            'INSERT INTO weekends(user_id, date) VALUES(?,?)',
            [(user_id, d) for d in sel]
        )
        conn.commit()
        await query.edit_message_text(f'✅ Выходные сохранены: {sorted(sel)}')

    elif data == 'view_weekends':
        cursor.execute('SELECT DISTINCT user_id FROM weekends')
        users = [r[0] for r in cursor.fetchall()]
        if not users:
            await context.bot.send_message(chat_id=query.message.chat_id, text='Пока никто не сохранил выходные.')
            return
        sets = []
        for u in users:
            cursor.execute('SELECT date FROM weekends WHERE user_id = ?', (u,))
            sets.append({r[0] for r in cursor.fetchall()})
        common = set.intersection(*sets)
        msg = 'Нет общих выходных.' if not common else 'Общие выходные даты:\n' + '\n'.join(sorted(common))
        await context.bot.send_message(chat_id=query.message.chat_id, text=msg)


def main():
    token = os.getenv('BOT_TOKEN')
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start_or_message))
    app.add_handler(MessageHandler(filters.ALL, start_or_message))
    app.add_handler(CallbackQueryHandler(calendar_callback, pattern='^calendar$'))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info('Bot started...')
    app.run_polling()

if __name__ == '__main__':
    main()
