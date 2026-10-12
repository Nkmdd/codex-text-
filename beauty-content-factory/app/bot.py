"""Telegram intake: /start, /new, send videos/photos, /title, /style, /duration, /make."""
import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from app.core import (EXTENSIONS, MAX_FILES, MAX_UPLOAD_MB, get_job, init_db,
                      job_dir, new_id, submit)

logging.basicConfig(level=logging.INFO)
log=logging.getLogger('factory.telegram')
ALLOWED={x.strip() for x in os.getenv('ALLOWED_TELEGRAM_USERS','').split(',') if x.strip()}


def permitted(update):
    return str(update.effective_user.id) in ALLOWED


async def start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f'Привет! Твой Telegram ID: {update.effective_user.id}\n'
        'После добавления ID в настройки бота: /new → отправляй видео/фото → /make.\n'
        'Максимум 12 файлов. Для больших исходников удобнее веб-загрузка.')


async def new(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):
        await update.message.reply_text('Доступ пока закрыт. Пришли администратору свой ID из /start.')
        return
    job=new_id()
    ctx.user_data.clear()
    ctx.user_data.update(job_id=job,sources=[],title='Красота в деталях',style='soft',duration=15)
    await update.message.reply_text('Новый монтаж 🎬 Отправляй видео или фотографии по одному, затем /make.\n'
                                    'Название: /title Новый текст\n'
                                    'Стиль: /style soft|minimal|editorial\n'
                                    'Длина: /duration 15|30|45')


async def title(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):return
    if not ctx.user_data.get('job_id'):
        await update.message.reply_text('Сначала /new');return
    ctx.user_data['title']=' '.join(ctx.args)[:120]
    await update.message.reply_text('Заголовок сохранён.')


async def style(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):return
    if not ctx.user_data.get('job_id'):
        await update.message.reply_text('Сначала /new');return
    value=(ctx.args or [''])[0].lower()
    if value not in {'soft','minimal','editorial'}:
        await update.message.reply_text('Варианты: /style soft или minimal или editorial');return
    ctx.user_data['style']=value
    await update.message.reply_text('Стиль: '+value)


async def duration(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):return
    if not ctx.user_data.get('job_id'):
        await update.message.reply_text('Сначала /new');return
    value=(ctx.args or [''])[0]
    if value not in {'15','30','45'}:
        await update.message.reply_text('Варианты: /duration 15, 30, 45');return
    ctx.user_data['duration']=int(value)
    await update.message.reply_text('Длительность: '+value+' секунд')


async def media(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):return
    if not ctx.user_data.get('job_id'):
        await update.message.reply_text('Начни с /new');return
    if len(ctx.user_data.get('sources',[]))>=MAX_FILES:
        await update.message.reply_text('Максимум 12 исходников. Отправь /make.');return
    msg=update.effective_message
    tg_media=msg.video or msg.document or (msg.photo[-1] if msg.photo else None)
    if not tg_media:
        return
    if msg.photo:
        extension='.jpg'
    elif msg.video:
        extension=Path(msg.video.file_name or 'video.mp4').suffix.lower() or '.mp4'
    else:
        extension=Path(msg.document.file_name or '').suffix.lower()
    if extension not in EXTENSIONS:
        await msg.reply_text('Принимаю MP4/MOV/WEBM и JPG/PNG.');return
    if tg_media.file_size and tg_media.file_size>20*1024*1024:
        await msg.reply_text('Этот файл слишком большой для обычного Telegram Bot API. Используй веб-страницу.');return
    root=job_dir(ctx.user_data['job_id'])
    dest=root/f'source-{len(ctx.user_data["sources"]):02d}{extension}'
    try:
        f=await ctx.bot.get_file(tg_media.file_id)
        await f.download_to_drive(custom_path=str(dest))
    except Exception as e:
        log.warning('Download failed %s',e)
        await msg.reply_text('Не удалось скачать видео. Для больших файлов используй веб-загрузку.');return
    ctx.user_data['sources'].append(str(dest))
    await msg.reply_text(f'Получено {len(ctx.user_data["sources"])} файлов. Продолжай или /make.')


async def make(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):return
    data=ctx.user_data
    if not data.get('job_id') or not data.get('sources'):
        await update.message.reply_text('Нет исходников. /new → отправь видео → /make');return
    job_id=data['job_id']
    try:
        submit(job_id,title=data.get('title',''),style=data.get('style','soft'),
               duration=data.get('duration',15),sources=data['sources'],
               owner='tg:'+str(update.effective_chat.id))
    except Exception as e:
        await update.message.reply_text('Ошибка: '+str(e));return
    ctx.user_data.clear()
    await update.message.reply_text('Задача в очереди 🛠 ID '+job_id+'\n'
                                    'Пришлю результат сюда. Проверить: /status '+job_id)


async def status(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not permitted(update):return
    job=get_job((ctx.args or [''])[0])
    if not job or job['owner']!='tg:'+str(update.effective_chat.id):
        await update.message.reply_text('Задача не найдена.');return
    await update.message.reply_text('Статус: '+job['status']+
                      (('\nОшибка: '+job['error'][:250]) if job['error'] else ''))


def main():
    token=os.getenv('TELEGRAM_BOT_TOKEN','')
    if not token:
        raise RuntimeError('Set TELEGRAM_BOT_TOKEN in .env')
    init_db()
    app=Application.builder().token(token).build()
    for cmd,func in [('start',start),('id',start),('new',new),('title',title),
                     ('style',style),('duration',duration),('make',make),('status',status)]:
        app.add_handler(CommandHandler(cmd,func))
    app.add_handler(MessageHandler(filters.VIDEO|filters.PHOTO|filters.Document.ALL,media))
    app.run_polling(drop_pending_updates=False)

if __name__=='__main__':
    main()
