import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(os.getenv('DATA_DIR', '/data'))
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '350'))
MAX_FILES = int(os.getenv('MAX_FILES', '12'))
STYLES = {'minimal', 'editorial', 'soft'}
EXTENSIONS = {'.mp4', '.mov', '.m4v', '.webm', '.jpg', '.jpeg', '.png'}
MUSIC_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.aac'}


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / 'factory.db', timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn


def init_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          status TEXT NOT NULL, owner TEXT NOT NULL, title TEXT NOT NULL,
          style TEXT NOT NULL, duration INTEGER NOT NULL, sources TEXT NOT NULL,
          music TEXT, output TEXT, error TEXT)''')


def job_dir(job_id):
    if not re.fullmatch(r'[0-9a-f]{32}', job_id):
        raise ValueError('invalid job id')
    p = DATA / 'jobs' / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_id():
    return uuid.uuid4().hex


def submit(job_id, *, title, style, duration, sources, owner='web', music=None):
    if style not in STYLES or duration not in {15, 30, 45}:
        raise ValueError('invalid rendering settings')
    if not sources or len(sources) > MAX_FILES:
        raise ValueError('invalid number of files')
    for path in sources:
        if not Path(path).is_file() or Path(path).suffix.lower() not in EXTENSIONS:
            raise ValueError('invalid input file')
    if music and (not Path(music).is_file() or Path(music).suffix.lower() not in MUSIC_EXTENSIONS):
        raise ValueError('invalid music file')
    with db() as c:
        c.execute('''INSERT INTO jobs (id,created_at,updated_at,status,owner,title,style,duration,sources,music)
          VALUES (?,?,?,?,?,?,?,?,?,?)''', (job_id, now(), now(), 'queued', owner, title[:120],
                                          style, duration, json.dumps(sources), music))
    return job_id


def get_job(job_id):
    with db() as c:
        r = c.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    return dict(r) if r else None


def claim_job():
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            return None
        c.execute('UPDATE jobs SET status=?,updated_at=? WHERE id=?', ('running', now(), row['id']))
        return get_job(row['id'])


def finish_job(job_id, *, output=None, error=None):
    with db() as c:
        c.execute('UPDATE jobs SET status=?,updated_at=?,output=?,error=? WHERE id=?',
                  ('failed' if error else 'done', now(), str(output) if output else None,
                   str(error)[:1500] if error else None, job_id))
