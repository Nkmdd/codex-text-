import hmac
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from app.core import (EXTENSIONS, MAX_FILES, MAX_UPLOAD_MB, MUSIC_EXTENSIONS,
                      STYLES, get_job, init_db, job_dir, new_id, submit)

app = FastAPI(title='Beauty Content Factory', docs_url=None, redoc_url=None)
COOKIE='factory_session'
PASSWORD=os.getenv('WEB_UPLOAD_PASSWORD', '')


@app.on_event('startup')
def startup():
    init_db()


def authenticated(request):
    if not PASSWORD:
        return False
    desired=hmac.digest(PASSWORD.encode(), b'beauty-factory-session-v1', 'sha256').hex()
    return hmac.compare_digest(request.cookies.get(COOKIE, ''), desired)


def require_auth(request):
    if not authenticated(request):
        raise HTTPException(status_code=401, detail='Сначала войдите в систему')


@app.get('/healthz')
def health():
    return {'ok': True}


LOGIN='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Beauty Factory</title><style>
body{background:#111017;color:#fff;font:16px system-ui;margin:0;padding:25px}main{max-width:520px;margin:10vh auto}h1{font-size:34px}p{color:#b8b5c2}input,button{width:100%;box-sizing:border-box;padding:15px;border-radius:12px;font-size:16px;margin-top:12px;border:1px solid #777;background:#24222b;color:white}button{border:0;background:#d986b0;color:#100b15;font-weight:700}</style></head><body><main><h1>Beauty Factory ✨</h1><p>Ваш личный конвейер Reels. Введите ключ доступа.</p><form method="post" action="/login"><input type="password" name="password" placeholder="Ключ доступа" required><button>Войти</button></form></main></body></html>'''
PAGE='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Beauty Factory</title><style>
:root{color-scheme:dark}body{background:#101016;color:#f9f5f8;font:16px system-ui;margin:0;padding:20px}main{max-width:660px;margin:auto}h1{font-size:34px;margin-bottom:6px}h2{font-size:20px}p,small{color:#bcb8c5}.box{background:#201f29;padding:22px;border-radius:18px;margin:16px 0}input,select,button{display:block;width:100%;box-sizing:border-box;padding:14px;margin:10px 0 18px;background:#33313e;color:white;border:1px solid #585363;border-radius:12px;font-size:16px}button{background:#e5a2c1;border:0;color:#161019;font-weight:800;cursor:pointer}button:disabled{opacity:.6}label{font-weight:600}#status{white-space:pre-wrap;overflow-wrap:anywhere;color:#d3d1de}a{color:#efa8cf}.notice{border-left:4px solid #e5a2c1;padding-left:12px}</style></head><body><main><h1>Beauty Factory ✨</h1><p>Снимаешь ты — монтирует система.</p><div class="box"><h2>Новый Reels</h2><form id="send">
<label>Видео и фотографии (до 12 файлов)</label><input name="files" type="file" accept="video/*,image/*" multiple required>
<label>Заголовок в начале</label><input name="title" maxlength="120" value="Красота в деталях">
<label>Стиль</label><select name="style"><option value="soft">Soft Beauty</option><option value="minimal">Clean Minimal</option><option value="editorial">Bold Editorial</option></select>
<label>Длина ролика</label><select name="duration"><option value="15">15 секунд</option><option value="30">30 секунд</option><option value="45">45 секунд</option></select>
<label>Музыка (необязательно, только своя/лицензированная)</label><input type="file" name="music" accept="audio/*">
<button id="button">Собрать Reels</button></form><p class="notice">Это шаблонный монтаж MVP. Смысловая нарезка и автоматические субтитры будут добавлены позже.</p><div id="status"></div></div>
</main><script>
const f=document.getElementById('send'),s=document.getElementById('status'),b=document.getElementById('button');
f.addEventListener('submit',async(e)=>{e.preventDefault();b.disabled=true;s.textContent='Загружаем исходники…';
try {const files=f.elements.files.files;if(files.length>12)throw Error('Максимум 12 файлов');
let data=new FormData(f);if(!f.elements.music.files.length)data.delete('music');
const r=await fetch('/jobs',{method:'POST',body:data});const result=await r.json();if(!r.ok)throw Error(JSON.stringify(result.detail));
s.textContent='Материалы в очереди: '+result.id; poll(result.id);
}catch(err){s.textContent='Ошибка: '+err.message;b.disabled=false;}});
async function poll(id){try{const r=await fetch('/jobs/'+id);const v=await r.json();if(!r.ok)throw Error('Не удалось проверить статус');
s.textContent='Монтаж: '+v.status+' · '+id;
if(v.status==='done'){s.innerHTML='🎉 Готово! <a href="/download/'+id+'">Скачать MP4</a>';b.disabled=false;}
else if(v.status==='failed'){s.textContent='Ошибка монтажа: '+v.error;b.disabled=false;}
else setTimeout(()=>poll(id),3000);}catch(e){s.textContent=e.message;b.disabled=false;}}
</script></body></html>'''


@app.get('/', response_class=HTMLResponse)
def index(request:Request):
    if not PASSWORD:
        return HTMLResponse('<h2>Set WEB_UPLOAD_PASSWORD before using this service.</h2>',status_code=503)
    return PAGE if authenticated(request) else LOGIN


@app.post('/login')
async def login(password:str=Form(...)):
    if not PASSWORD or not hmac.compare_digest(password,PASSWORD):
        raise HTTPException(status_code=401,detail='Неверный пароль')
    r=RedirectResponse('/',status_code=303)
    r.set_cookie(COOKIE,hmac.digest(PASSWORD.encode(),b'beauty-factory-session-v1','sha256').hex(),
                 httponly=True,secure=os.getenv('COOKIE_SECURE','true').lower()=='true',
                 samesite='strict',max_age=3600*24*14)
    return r


async def save(upload:UploadFile,dest:Path,limit:int):
    size=0
    with open(dest,'wb') as file:
        while True:
            chunk=await upload.read(1024*1024)
            if not chunk:break
            size+=len(chunk)
            if size>limit:
                dest.unlink(missing_ok=True)
                raise HTTPException(413,f'Файл больше {limit//1024//1024} МБ')
            file.write(chunk)
    if size==0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400,'Пустой файл')


@app.post('/jobs')
async def jobs(request:Request,files:list[UploadFile]=File(...),title:str=Form(''),
               style:str=Form('soft'),duration:int=Form(15),music:UploadFile|None=File(None)):
    require_auth(request)
    if len(files)<1 or len(files)>MAX_FILES:
        raise HTTPException(400,f'Нужно от 1 до {MAX_FILES} файлов')
    if style not in STYLES or duration not in {15,30,45}:
        raise HTTPException(400,'Неверные настройки монтажа')
    if any(Path(f.filename or '').suffix.lower() not in EXTENSIONS for f in files):
        raise HTTPException(400,'Неподдерживаемый формат файла')
    job_id=new_id()
    root=job_dir(job_id)
    paths=[]
    for i,f in enumerate(files):
        suffix=Path(f.filename or '').suffix.lower()
        dest=root/f'source-{i:02d}{suffix}'
        await save(f,dest,MAX_UPLOAD_MB*1024*1024)
        paths.append(str(dest))
    sound=None
    if music and music.filename:
        extension=Path(music.filename).suffix.lower()
        if extension not in MUSIC_EXTENSIONS:
            raise HTTPException(400,'Музыка: поддерживаются MP3, M4A, WAV, AAC')
        sound=root/f'music{extension}'
        await save(music,sound,MAX_UPLOAD_MB*1024*1024)
    submit(job_id,title=title,style=style,duration=duration,sources=paths,
           music=str(sound) if sound else None)
    return JSONResponse({'id':job_id,'status':'queued'},status_code=202)


@app.get('/jobs/{job_id}')
def status(request:Request,job_id:str):
    require_auth(request)
    job=get_job(job_id)
    if not job or job['owner']!='web':
        raise HTTPException(404,'Не найдено')
    return {'id':job_id,'status':job['status'],'error':job['error']}


@app.get('/download/{job_id}')
def download(request:Request,job_id:str):
    require_auth(request)
    job=get_job(job_id)
    if not job or job['owner']!='web' or job['status']!='done' or not job['output']:
        raise HTTPException(404,'Не готово')
    return FileResponse(job['output'],media_type='video/mp4',filename='beauty-reels.mp4')
