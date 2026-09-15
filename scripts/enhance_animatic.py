"""Add procedural music and export landscape/vertical animatic versions."""
import math
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "animatic_work"
VIDEOS = ROOT / "videos"
SOURCE = VIDEOS / "nameless_local_animatic.mp4"
SCORED = VIDEOS / "nameless_local_animatic_scored.mp4"
VERTICAL = VIDEOS / "nameless_local_animatic_vertical.mp4"
PREVIEW = VIDEOS / "nameless_storyboard_preview.jpg"
BGM = WORK / "procedural_score.wav"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT = r"C:\Windows\Fonts\msyh.ttc"
DURATION = 54.0
SAMPLE_RATE = 44100


def run(args):
    subprocess.run(args, check=True)


def create_score():
    count = int(DURATION * SAMPLE_RATE)
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    music = np.zeros(count, dtype=np.float64)
    # Dark evolving drone built from consonant low frequencies.
    for frequency, amplitude in [(55.0, 0.22), (82.41, 0.12), (110.0, 0.06)]:
        phase = 0.7 * np.sin(2 * np.pi * 0.035 * t)
        music += amplitude * np.sin(2 * np.pi * frequency * t + phase)
    music *= 0.65 + 0.25 * np.sin(2 * np.pi * 0.018 * t - 1.2)
    # Quiet cinematic pulse every two seconds.
    for beat in np.arange(1.0, DURATION, 2.0):
        start = int(beat * SAMPLE_RATE)
        length = min(int(0.7 * SAMPLE_RATE), count - start)
        local = np.arange(length) / SAMPLE_RATE
        pulse = np.sin(2 * np.pi * (62 - 18 * local) * local)
        pulse *= np.exp(-5.2 * local) * 0.22
        music[start:start + length] += pulse
    # Soft noise swells at scene boundaries.
    rng = np.random.default_rng(42)
    for boundary in [0, 5.2, 11.4, 17.9, 25.8, 32.2, 38.4, 45.0, 53.8]:
        start = max(0, int((boundary - 0.5) * SAMPLE_RATE))
        length = min(int(1.0 * SAMPLE_RATE), count - start)
        if length <= 0:
            continue
        envelope = np.sin(np.linspace(0, math.pi, length)) ** 2
        music[start:start + length] += rng.normal(0, 0.025, length) * envelope
    fade = int(2.0 * SAMPLE_RATE)
    music[:fade] *= np.linspace(0, 1, fade)
    music[-fade:] *= np.linspace(1, 0, fade)
    music = np.tanh(music * 1.3)
    stereo = np.column_stack([music, np.roll(music, 17)])
    pcm = np.int16(np.clip(stereo, -1, 1) * 32767)
    with wave.open(str(BGM), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm.tobytes())


def create_preview():
    thumbs = []
    for index in range(1, 9):
        image = Image.open(WORK / f"scene_{index:02}.png").convert("RGB")
        image.thumbnail((480, 270), Image.Resampling.LANCZOS)
        thumbs.append(image.copy())
    canvas = Image.new("RGB", (1000, 1240), (8, 10, 15))
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(FONT, 48)
    small_font = ImageFont.truetype(FONT, 24)
    draw.text((50, 30), "《无名之人》八镜头动态分镜", font=title_font, fill="white")
    for i, image in enumerate(thumbs):
        x = 20 + (i % 2) * 490
        y = 115 + (i // 2) * 280
        canvas.paste(image, (x, y))
        draw.text((x + 8, y + 235), f"镜头 {i + 1:02}", font=small_font, fill=(240, 240, 240))
    canvas.save(PREVIEW, quality=92)


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source video: {SOURCE}")
    create_score()
    create_preview()
    run([
        FFMPEG, "-y", "-i", str(SOURCE), "-i", str(BGM),
        "-filter_complex",
        "[0:a]aresample=48000:async=1:first_pts=0,aformat=channel_layouts=stereo[narr];"
        "[1:a]aresample=48000:async=1:first_pts=0,volume=0.14[bg];"
        "[narr][bg]amix=inputs=2:duration=first:dropout_transition=2,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000:async=1:first_pts=0,"
        "aformat=sample_rates=48000:channel_layouts=stereo[a]",
        "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
        "-ar", "48000", "-ac", "2", "-b:a", "160k", "-movflags", "+faststart", str(SCORED),
    ])
    run([
        FFMPEG, "-y", "-i", str(SCORED),
        "-vf", "scale=1080:608,pad=1080:1920:0:656:color=0x080a0f",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy",
        "-movflags", "+faststart", str(VERTICAL),
    ])
    print(f"Created: {SCORED}")
    print(f"Created: {VERTICAL}")
    print(f"Created: {PREVIEW}")


if __name__ == "__main__":
    main()
