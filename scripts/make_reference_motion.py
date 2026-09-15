"""Render a reference-bound 2.5D motion animatic from the local protagonist photos."""
import hashlib
import json
import math
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
PHOTOS = ROOT / "photos"
WORK = ROOT / "reference_motion_work"
VIDEOS = ROOT / "videos"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
W, H, FPS = 720, 1280, 20
REFERENCES = [PHOTOS / f"{i}.jpg" for i in range(1, 4)]
SCENES = [
    ("弃子", "巴黎雨夜，他的名字被家族抹去。", 0, "rain"),
    ("交易", "亲生父亲用一句成交，将他卖给哈夫克。", 1, "deal"),
    ("炼狱", "冰冷电极刺入后颈，十二个孩子只剩他醒着。", 0, "lab"),
    ("幸存者", "适配度百分之百。他们想制造兵器，却唤醒反抗。", 1, "scan"),
    ("背叛", "被篡改的录像摧毁信任，从此他只相信自己的刀。", 2, "glitch"),
    ("兵器", "六年后，编号H42成为战场上无声的幽灵。", 0, "battle"),
    ("了断", "燃烧的车旁，他转身离开，也烧掉了旧日姓名。", 1, "fire"),
    ("归途", "脑机终于摘除。迎着日出，他成为自己的主人。", 2, "sunrise"),
]


def run(args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def fit_cover(image, size, scale=1.0, pan_x=0.0, pan_y=0.0):
    tw, th = size
    ratio = max(tw / image.width, th / image.height) * scale
    resized = image.resize((math.ceil(image.width * ratio), math.ceil(image.height * ratio)), Image.Resampling.LANCZOS)
    max_x, max_y = max(0, resized.width - tw), max(0, resized.height - th)
    left = int(np.clip(max_x * (0.5 + pan_x), 0, max_x))
    top = int(np.clip(max_y * (0.5 + pan_y), 0, max_y))
    return resized.crop((left, top, left + tw, top + th))


def subject_layer(image):
    fitted = fit_cover(image, (W, H), scale=1.025)
    mask = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((W * 0.08, -H * 0.08, W * 0.92, H * 1.08), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(42))
    fitted.putalpha(mask)
    return fitted


def transform_layer(layer, scale, dx, dy):
    sw, sh = int(W * scale), int(H * scale)
    moved = layer.resize((sw, sh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(moved, (int((W - sw) / 2 + dx), int((H - sh) / 2 + dy)))
    return canvas


def add_grade(frame, tint, amount=0.18):
    overlay = Image.new("RGB", frame.size, tint)
    frame = Image.blend(frame, overlay, amount)
    return ImageEnhance.Contrast(frame).enhance(1.12)


def draw_effects(frame, kind, tick, rng):
    draw = ImageDraw.Draw(frame, "RGBA")
    if kind == "rain":
        for i in range(42):
            x = (i * 79 + tick * 19) % (W + 100) - 50
            y = (i * 137 + tick * 31) % (H + 180) - 90
            draw.line((x, y, x - 18, y + 72), fill=(175, 215, 255, 105), width=2)
    elif kind in {"lab", "scan"}:
        y = int((tick * 11) % H)
        draw.rectangle((0, y - 7, W, y + 7), fill=(85, 255, 244, 80))
        for line_y in range(0, H, 18):
            draw.line((0, line_y, W, line_y), fill=(110, 230, 230, 20), width=1)
        if kind == "scan":
            draw.text((W - 205, 126), "MATCH 100%", font=ImageFont.truetype(str(BOLD), 27), fill=(130, 255, 242, 225))
    elif kind == "glitch":
        for band in range(7):
            y = (band * 181 + tick * 23) % H
            color = (255, 40, 80, 45) if band % 2 else (30, 235, 255, 45)
            draw.rectangle((0, y, W, y + 8 + band * 2), fill=color)
    elif kind == "battle":
        for i in range(34):
            x = (i * 113 + tick * 13) % W
            y = (i * 61 - tick * 17) % H
            r = 2 + i % 5
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(225, 189, 110, 75))
    elif kind == "fire":
        for i in range(48):
            x = (i * 97 + tick * 7) % W
            y = H - ((i * 83 + tick * (7 + i % 5)) % 520)
            r = 2 + i % 7
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(255, 92 + i % 90, 18, 120))
    elif kind == "sunrise":
        cx, cy = W // 2, int(H * 0.32)
        for a in range(0, 360, 18):
            rad = math.radians(a + tick * 0.2)
            draw.line((cx, cy, cx + math.cos(rad) * 660, cy + math.sin(rad) * 660), fill=(255, 190, 80, 22), width=9)
        draw.ellipse((cx-85, cy-85, cx+85, cy+85), fill=(255, 194, 83, 80))
    elif kind == "deal":
        draw.rectangle((42, 180, 250, 480), fill=(245, 240, 218, 45), outline=(255, 220, 160, 100), width=3)
        draw.ellipse((455, 220, 560, 325), outline=(229, 182, 73, 185), width=10)


def render_frame(reference, scene_index, kind, tick, total_frames):
    progress = tick / max(1, total_frames - 1)
    phase = progress * math.tau
    shake = 0
    if kind in {"battle", "glitch", "fire"}:
        shake = math.sin(tick * 1.7) * (5 if kind == "battle" else 3)
    pan_x = 0.08 * math.sin(phase * 0.62 + scene_index)
    pan_y = 0.035 * math.cos(phase * 0.78 + scene_index * 0.4)
    bg = fit_cover(reference, (W, H), 1.08 + 0.045 * progress, pan_x, pan_y)
    bg = bg.filter(ImageFilter.GaussianBlur(8))
    bg = ImageEnhance.Brightness(bg).enhance(0.58)
    fg = subject_layer(reference.copy())
    breathing = 1.0 + 0.012 * math.sin(phase * 2.0)
    fg = transform_layer(fg, 1.015 + 0.035 * progress + breathing - 1.0, shake + 10 * math.sin(phase), 7 * math.sin(phase * 2.0))
    frame = bg.convert("RGBA")
    frame.alpha_composite(fg)
    grades = {
        "rain": ((25, 55, 95), 0.19), "deal": ((95, 40, 30), 0.17),
        "lab": ((20, 100, 105), 0.19), "scan": ((20, 80, 100), 0.16),
        "glitch": ((70, 25, 80), 0.17), "battle": ((96, 75, 45), 0.17),
        "fire": ((125, 44, 12), 0.21), "sunrise": ((135, 89, 28), 0.18),
    }
    tint, amount = grades[kind]
    frame = add_grade(frame.convert("RGB"), tint, amount).convert("RGBA")
    draw_effects(frame, kind, tick, np.random.default_rng(scene_index * 10000 + tick))
    return frame


def add_text(frame, index, title, subtitle, progress):
    draw = ImageDraw.Draw(frame, "RGBA")
    title_font = ImageFont.truetype(str(BOLD), 42)
    sub_font = ImageFont.truetype(str(FONT), 31)
    draw.rectangle((0, 0, W, 105), fill=(0, 0, 0, 125))
    draw.text((35, 25), f"0{index + 1}  {title}", font=title_font, fill=(255, 255, 255, 245))
    bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
    text_w = bbox[2] - bbox[0]
    pad = 18
    x = max(18, (W - text_w) // 2)
    y = H - 118
    draw.rounded_rectangle((x-pad, y-pad, x+text_w+pad, y+52), radius=15, fill=(0, 0, 0, 165))
    draw.text((x, y), subtitle, font=sub_font, fill=(250, 250, 250, 255))
    if progress < 0.08:
        alpha = int(255 * progress / 0.08)
        frame.putalpha(alpha)
    elif progress > 0.92:
        alpha = int(255 * (1 - progress) / 0.08)
        frame.putalpha(max(0, alpha))
    return frame.convert("RGB")


def wav_duration(path):
    with wave.open(str(path), "rb") as source:
        return source.getnframes() / source.getframerate()


def ensure_narration():
    payload = [{"index": i + 1, "text": scene[1]} for i, scene in enumerate(SCENES)]
    metadata = WORK / "narration.json"
    metadata.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8-sig")
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "make_narration.ps1"), str(metadata), str(WORK)])


def render_scene(index, scene):
    title, subtitle, reference_index, kind = scene
    reference = Image.open(REFERENCES[reference_index]).convert("RGB")
    audio = WORK / f"scene_{index + 1:02}.wav"
    duration = max(5.6, wav_duration(audio) + 0.65)
    total_frames = math.ceil(duration * FPS)
    raw = WORK / f"scene_{index + 1:02}_raw.mp4"
    clip = WORK / f"scene_{index + 1:02}.mp4"
    command = [
        FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", str(raw),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    first_frame = None
    last_frame = None
    for tick in range(total_frames):
        progress = tick / max(1, total_frames - 1)
        frame = render_frame(reference, index, kind, tick, total_frames)
        frame = add_text(frame, index, title, subtitle, progress)
        if tick == 1:
            first_frame = frame.copy()
        if tick == total_frames - 2:
            last_frame = frame.copy()
        process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"FFmpeg frame encoding failed for scene {index + 1}")
    run([
        FFMPEG, "-y", "-i", str(raw), "-i", str(audio),
        "-filter_complex", "[1:a]aresample=48000:async=1:first_pts=0,"
        "aformat=channel_layouts=stereo,apad[a]",
        "-map", "0:v:0", "-map", "[a]", "-t", f"{duration:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-b:a", "160k", str(clip),
    ])
    motion = float(np.asarray(ImageChops.difference(first_frame, last_frame)).mean())
    return clip, duration, motion


def reference_similarity(frame, reference):
    region = frame.crop((0, 110, W, H - 130)).convert("L").resize((72, 104), Image.Resampling.BILINEAR)
    expected = fit_cover(reference, (W, H), 1.025).crop((0, 110, W, H - 130)).convert("L").resize((72, 104), Image.Resampling.BILINEAR)
    a = np.asarray(region, dtype=np.float64).ravel()
    b = np.asarray(expected, dtype=np.float64).ravel()
    if a.std() < 1e-6 or b.std() < 1e-6:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    missing = [str(path) for path in REFERENCES if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Required protagonist references are missing; refusing unrelated fallback: " + ", ".join(missing)
        )
    WORK.mkdir(exist_ok=True)
    VIDEOS.mkdir(exist_ok=True)
    ensure_narration()
    manifest = {"character": "无名", "policy": "required-no-fallback", "references": [], "scenes": []}
    for path in REFERENCES:
        with Image.open(path) as image:
            manifest["references"].append({
                "path": str(path), "sha256": file_sha256(path),
                "width": image.width, "height": image.height,
            })
    clips = []
    quality = []
    for index, scene in enumerate(SCENES):
        print(f"Rendering [{index + 1}/8] {scene[0]} from {REFERENCES[scene[2]].name}", flush=True)
        clip, duration, motion = render_scene(index, scene)
        clips.append(clip)
        reference = Image.open(REFERENCES[scene[2]]).convert("RGB")
        probe = render_frame(reference, index, scene[3], 30, max(120, int(duration * FPS))).convert("RGB")
        similarity = reference_similarity(probe, reference)
        manifest["scenes"].append({
            "scene": index + 1, "title": scene[0], "reference": str(REFERENCES[scene[2]]),
            "effect": scene[3], "duration": round(duration, 3),
        })
        quality.append({
            "scene": index + 1, "title": scene[0], "reference": REFERENCES[scene[2]].name,
            "motion_mean_abs_difference": round(motion, 3),
            "reference_correlation": round(similarity, 4),
        })
    (WORK / "reference-binding-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    concat = WORK / "concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in clips), encoding="utf-8")
    vertical_base = WORK / "nameless_reference_vertical_base.mp4"
    vertical = VIDEOS / "nameless_reference_motion_vertical.mp4"
    horizontal = VIDEOS / "nameless_reference_motion_horizontal.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(vertical_base)])
    score = ROOT / "animatic_work" / "procedural_score.wav"
    if score.exists():
        run([
            FFMPEG, "-y", "-i", str(vertical_base), "-stream_loop", "-1", "-i", str(score),
            "-filter_complex", "[0:a]aresample=48000:async=1:first_pts=0[n];"
            "[1:a]aresample=48000:async=1:first_pts=0,volume=0.11[b];"
            "[n][b]amix=inputs=2:duration=first:dropout_transition=2,"
            "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000:async=1:first_pts=0[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
            "-ar", "48000", "-ac", "2", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(vertical),
        ])
    else:
        run([FFMPEG, "-y", "-i", str(vertical_base), "-c", "copy", "-movflags", "+faststart", str(vertical)])
    run([
        FFMPEG, "-y", "-i", str(vertical), "-filter_complex",
        "[0:v]split=2[front][back];[back]scale=1280:720:force_original_aspect_ratio=increase,"
        "crop=1280:720,boxblur=24:12[bg];[front]scale=-2:720[fg];"
        "[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]",
        "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "copy", "-movflags", "+faststart", str(horizontal),
    ])
    passed = all(item["motion_mean_abs_difference"] >= 4.0 and item["reference_correlation"] >= 0.35 for item in quality)
    report = {"passed": passed, "thresholds": {"motion": 4.0, "correlation": 0.35}, "scenes": quality}
    (WORK / "reference-motion-quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not passed:
        raise RuntimeError(f"Reference/motion quality gate failed: {report}")
    print(f"Created: {vertical}")
    print(f"Created: {horizontal}")
    print(f"Quality: {WORK / 'reference-motion-quality.json'}")


if __name__ == "__main__":
    main()

