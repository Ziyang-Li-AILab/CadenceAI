"""Create a zero-cost local animatic with Chinese narration and subtitles."""
import json
import math
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "animatic_work"
OUT = ROOT / "videos" / "nameless_local_animatic.mp4"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
W, H, FPS = 1280, 720, 24
SCENES = [
    ("弃子", "巴黎雨夜，他的名字被家族抹去。", (15, 22, 42), (63, 88, 132), "attic"),
    ("交易", "亲生父亲用一句成交，将他卖给哈夫克。", (31, 18, 22), (125, 70, 48), "deal"),
    ("炼狱", "冰冷电极刺入后颈，十二个孩子只剩他醒着。", (8, 27, 31), (42, 143, 151), "lab"),
    ("幸存者", "适配度百分之百。他们想制造兵器，却唤醒反抗。", (14, 24, 35), (56, 174, 193), "screen"),
    ("背叛", "被篡改的录像摧毁信任，从此他只相信自己的刀。", (20, 15, 29), (112, 54, 125), "monitor"),
    ("兵器", "六年后，编号H42成为战场上无声的幽灵。", (20, 25, 24), (107, 105, 68), "battle"),
    ("了断", "燃烧的车旁，他转身离开，也烧掉了旧日姓名。", (39, 17, 8), (189, 67, 17), "fire"),
    ("归途", "脑机终于摘除。迎着日出，他成为自己的主人。", (23, 33, 45), (221, 145, 55), "sunrise"),
]

def font(path, size):
    return ImageFont.truetype(str(path), size)

def gradient(c1, c2):
    y = np.linspace(0, 1, H)[:, None, None]
    a, b = np.array(c1)[None, None, :], np.array(c2)[None, None, :]
    arr = np.repeat((a * (1-y) + b*y).astype("uint8"), W, axis=1)
    return Image.fromarray(arr, "RGB")

def silhouette(draw, x, ground, scale=1.0):
    dark = (5, 8, 12)
    draw.ellipse((x-24*scale, ground-190*scale, x+24*scale, ground-142*scale), fill=dark)
    draw.polygon([(x-28*scale, ground-145*scale), (x-60*scale, ground-25*scale),
                  (x+58*scale, ground-25*scale), (x+28*scale, ground-145*scale)], fill=dark)
    draw.line((x-24*scale, ground-30*scale, x-48*scale, ground), fill=dark, width=max(2, int(18*scale)))
    draw.line((x+24*scale, ground-30*scale, x+50*scale, ground), fill=dark, width=max(2, int(18*scale)))

def make_image(i, title, text, c1, c2, kind):
    img = gradient(c1, c2).filter(ImageFilter.GaussianBlur(0.6)); d = ImageDraw.Draw(img, "RGBA")
    rng = np.random.default_rng(i + 42)
    for _ in range(140):
        x, y = int(rng.integers(W)), int(rng.integers(H)); r = int(rng.integers(1, 4))
        d.ellipse((x-r, y-r, x+r, y+r), fill=(255, 255, 255, int(rng.integers(12, 55))))
    d.rectangle((0, 510, W, H), fill=(3, 6, 10, 180))
    if kind == "attic":
        d.rectangle((760, 100, 1120, 430), outline=(155, 183, 220, 170), width=8)
        for x in range(770, 1120, 28): d.line((x, 100, x-130, 430), fill=(190, 210, 240, 70), width=3)
        silhouette(d, 370, 555, .75)
    elif kind == "deal":
        d.ellipse((850, 390, 940, 480), outline=(230, 187, 77, 220), width=12); silhouette(d, 390, 560, .85)
        d.polygon([(705, 250), (930, 250), (900, 405), (675, 405)], fill=(220, 225, 215, 190))
    elif kind in {"lab", "screen", "monitor"}:
        for x in range(85, 1210, 230): d.rectangle((x, 100, x+180, 330), outline=(75, 220, 225, 130), width=5)
        silhouette(d, 640, 560, .95)
        if kind == "screen": d.text((500, 160), "100%", font=font(BOLD, 66), fill=(135, 255, 246, 235))
    elif kind == "battle":
        for x in range(0, W, 160): d.polygon([(x, 510), (x+85, int(rng.integers(340, 500))), (x+160, 510)], fill=(15, 18, 17, 210))
        silhouette(d, 640, 570, 1.05); d.ellipse((825, 250, 900, 290), outline=(215, 205, 134, 220), width=6)
    elif kind == "fire":
        for x, h in [(780, 180), (850, 280), (925, 210)]:
            d.polygon([(x-70, 520), (x, 520-h), (x+65, 520)], fill=(255, 104, 14, 190))
        silhouette(d, 430, 565, 1.0)
    else:
        d.ellipse((800, 70, 1120, 390), fill=(255, 184, 74, 170)); silhouette(d, 620, 560, 1.0)
    d.rectangle((0, 0, W, 105), fill=(0, 0, 0, 115)); d.text((64, 28), f"0{i+1}  {title}", font=font(BOLD, 42), fill="white")
    box = d.textbbox((0, 0), text, font=font(FONT, 34)); d.text(((W-(box[2]-box[0]))/2, 625), text, font=font(FONT, 34), fill=(245, 245, 245))
    img.save(WORK / f"scene_{i+1:02}.png")

def wav_duration(path):
    with wave.open(str(path), "rb") as f: return f.getnframes() / f.getframerate()

def run(args): subprocess.run(args, check=True)

def main():
    WORK.mkdir(exist_ok=True); OUT.parent.mkdir(exist_ok=True)
    meta = [{"index": i+1, "text": s[1]} for i, s in enumerate(SCENES)]
    (WORK / "narration.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8-sig")
    for i, scene in enumerate(SCENES): make_image(i, *scene)
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "make_narration.ps1"), str(WORK / "narration.json"), str(WORK)])
    clips = []
    for i in range(1, 9):
        audio, image, clip = WORK/f"scene_{i:02}.wav", WORK/f"scene_{i:02}.png", WORK/f"scene_{i:02}.mp4"
        duration = max(5.2, wav_duration(audio) + .55)
        frames = math.ceil(duration * FPS)
        vf = f"zoompan=z='min(zoom+0.0007,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5,format=yuv420p"
        run([FFMPEG,"-y","-loop","1","-i",str(image),"-i",str(audio),"-vf",vf,"-af","apad","-t",f"{duration:.3f}","-c:v","libx264","-preset","medium","-crf","20","-c:a","aac","-b:a","160k",str(clip)])
        clips.append(clip)
    concat = WORK / "concat.txt"; concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in clips), encoding="utf-8")
    run([FFMPEG,"-y","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(OUT)])
    print(f"Created: {OUT} ({OUT.stat().st_size/1024/1024:.1f} MB)")

if __name__ == "__main__": main()
