import logging
import os
import time
from pathlib import Path

import httpx
from app.core import init_db, claim_job, finish_job
from app.render import render

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('factory.worker')


def notify(job, message, video=None):
    if not job['owner'].startswith('tg:') or not os.getenv('TELEGRAM_BOT_TOKEN'):
        return
    chat_id = job['owner'].split(':', 1)[1]
    url = 'https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN']
    try:
        with httpx.Client(timeout=90) as c:
            if video and Path(video).stat().st_size <= 45 * 1024 * 1024:
                with open(video,'rb') as f:
                    r=c.post(url+'/sendVideo',data={'chat_id':chat_id,'caption':message,
                            'supports_streaming':'true'},files={'video':('reels.mp4',f,'video/mp4')})
            else:
                r=c.post(url+'/sendMessage',data={'chat_id':chat_id,'text':message})
            r.raise_for_status()
    except Exception as e:
        log.error('Telegram notification failed: %s',e)


def main():
    init_db()
    log.info('Worker online')
    while True:
        job = claim_job()
        if not job:
            time.sleep(2)
            continue
        try:
            result=render(job)
            finish_job(job['id'],output=result)
            log.info('Done %s',job['id'])
            notify(job,'Готово! Твой Reels 🎬',video=result)
        except Exception as exc:
            log.exception('Failed %s',job['id'])
            finish_job(job['id'],error=str(exc))
            notify(job,'Монтаж не удался. Ошибка сохранена: '+str(exc)[:200])

if __name__ == '__main__':
    main()
