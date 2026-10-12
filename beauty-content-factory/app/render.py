"""CPU-only, predictable MP4 assembly. No AI claims: this is template editing."""
import json
import math
import subprocess
from pathlib import Path

from app.core import job_dir

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
VIDEO = {'.mp4', '.mov', '.m4v', '.webm'}


def run(args):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=1800, check=False)
    if p.returncode:
        raise RuntimeError(f'ffmpeg/ffprobe exit {p.returncode}: {p.stderr[-1600:]}')
    return p.stdout


def probe(path):
    details = json.loads(run(['ffprobe', '-v', 'error', '-show_entries',
         'format=duration:stream=codec_type', '-of', 'json', str(path)]))
    streams = details.get('streams', [])
    if not any(x.get('codec_type') == 'video' for x in streams):
        raise ValueError('Input is not an image or video')
    return (float(details.get('format', {}).get('duration') or 0),
            any(x.get('codec_type') == 'audio' for x in streams))


def layout(style, title_file):
    # textfile avoids escaping Cyrillic, commas and punctuation in drawtext.
    base = (f'drawtext=fontfile={FONT}:textfile={title_file}:'
            'x=(w-text_w)/2:y=h*0.13:box=1:boxborderw=24:'
            "enable='lt(t,3)':expansion=none:")
    if style == 'soft':
        return base + 'fontsize=60:fontcolor=white:boxcolor=0xB65C7A@0.80'
    if style == 'editorial':
        return base + 'fontsize=76:fontcolor=0xFFFFFF:boxcolor=0x101010@0.85'
    return base + 'fontsize=60:fontcolor=white:boxcolor=black@0.55'


def render(job):
    workspace = job_dir(job['id'])
    sources = [Path(s) for s in json.loads(job['sources'])]
    if not sources:
        raise ValueError('Nothing to render')
    total = int(job['duration'])
    target = total / len(sources)
    title_file = workspace / 'title.txt'
    title_file.write_text(job['title'][:75].replace('\n', ' '), encoding='utf-8')
    parts = []
    for index, src in enumerate(sources):
        is_video = src.suffix.lower() in VIDEO
        duration, has_audio = probe(src)
        seconds = target
        if is_video and duration < 0.25:
            raise ValueError(f'Video too short: {src.name}')
        if is_video:
            # Loop shorter clips so the result keeps the requested duration.
            seek = max(0, (duration - seconds) * 0.22)
            ff = ['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y']
            if duration < seconds:
                ff += ['-stream_loop','-1']
            ff += ['-ss',f'{seek:.3f}','-i',str(src)]
        else:
            ff = ['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                  '-loop','1','-i',str(src)]
            has_audio = False
        if not has_audio:
            ff += ['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=44100']
        transforms = ['scale=1080:1920:force_original_aspect_ratio=decrease',
                      'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',
                      'setsar=1','fps=30','format=yuv420p']
        if index == 0 and job['title'].strip():
            transforms.append(layout(job['style'], title_file))
        vf = ','.join(transforms)
        out = workspace / f'part-{index:02d}.mp4'
        audio_source = '0:a:0' if has_audio else '1:a:0'
        ff += ['-filter_complex',f'[0:v:0]{vf}[v];[{audio_source}]aresample=44100,'
               'aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a]',
               '-map','[v]','-map','[a]','-t',f'{seconds:.4f}',
               '-c:v','libx264','-preset','veryfast','-crf','24','-threads','2',
               '-c:a','aac','-b:a','128k','-ar','44100','-ac','2',
               '-movflags','+faststart','-shortest',str(out)]
        run(ff)
        parts.append(out)
    manifest = workspace / 'cuts.txt'
    manifest.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts),encoding='utf-8')
    assembled = workspace / 'assembled.mp4'
    run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
         '-f','concat','-safe','0','-i',str(manifest),'-c','copy',
         '-movflags','+faststart',str(assembled)])
    output = workspace / 'reels.mp4'
    music = job.get('music')
    if music:
        run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
             '-i',str(assembled),'-stream_loop','-1','-i',music,
             '-filter_complex','[0:a]volume=1[a0];[1:a]volume=0.10[a1];'
                               '[a0][a1]amix=inputs=2:duration=first[out]',
             '-map','0:v','-map','[out]','-c:v','copy','-c:a','aac','-b:a','128k',
             '-shortest','-movflags','+faststart',str(output)])
    else:
        assembled.replace(output)
    return output
