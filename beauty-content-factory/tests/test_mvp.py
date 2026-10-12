import json
import subprocess

from app import core
from app.render import probe, render


def test_complete_montage(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    core.init_db()
    src=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i','color=c=blue:s=360x640:r=30',
         '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','2',
         '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)],check=True)
    jid=core.new_id()
    core.submit(jid,title='Мягкий макияж',style='soft',duration=15,
                sources=[str(src)])
    pending=core.claim_job()
    assert pending['id']==jid
    output=render(pending)
    length, audio=probe(output)
    assert output.exists() and output.stat().st_size>1000
    assert 14.5<length<15.5 and audio
    dims=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
                     '-show_entries','stream=width,height','-of','json',str(output)]))
    assert dims['streams'][0]['width']==1080
    assert dims['streams'][0]['height']==1920
    core.finish_job(jid,output=output)
    assert core.get_job(jid)['status']=='done'


def test_rejects_wrong_settings(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    core.init_db()
    s=tmp_path/'source.jpg';s.write_bytes(b'fake')
    import pytest
    with pytest.raises(ValueError):
        core.submit(core.new_id(),title='Test',style='invalid',duration=15,sources=[str(s)])
