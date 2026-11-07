"""New video: the real screen recording cut to the voiceover scenes, with subtitles. Does not touch the existing replay video."""
import os, subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 720
S = os.path.join(HERE, "screen_parts"); os.makedirs(S, exist_ok=True)
HEL = "/System/Library/Fonts/Helvetica.ttc"
def font(sz, bold=False): return ImageFont.truetype(HEL, sz, index=1 if bold else 0)
def run(*cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# (source start, source end, output seconds, subtitle = the voiceover line)
SCENES = [
    (40.0, 44.0, 4, "Staff post the problem in one shared room."),
    (44.0, 49.0, 5, "It checks the shop's back office: error E21."),
    (49.0, 52.0, 3, "Then it asks the memory agent I built."),
    (52.0, 58.0, 7, "We've seen this before, and the memory knows who said so."),
    (58.0, 61.0, 3, "An agent prepares a refund."),
    (62.0, 68.0, 7, "But it can't spend money. The refund waits for the owner."),
    (68.0, 70.0, 2, "Only the owner approves."),
    (73.0, 78.0, 5, "Approved. Applied. And recorded."),
]

def caption_png(text, path):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((0, 640, W, H), fill=(14, 14, 18, 255))
    f = font(32, True)
    while f.getlength(text) > W - 80: f = font(f.size - 2, True)
    d.text(((W - f.getlength(text)) // 2, 662), text, font=f, fill=(255, 255, 255, 255))
    b = font(18, True); label = "REAL SCREEN RECORDING"
    d.rounded_rectangle((84, 12, 84 + b.getlength(label) + 28, 44), 8, fill=(20, 20, 26, 220))
    d.text((98, 18), label, font=b, fill=(90, 200, 140, 255))
    im.save(path)

parts = []
# A: hook card from the existing silent replay render (0-5s), read-only
a = os.path.join(S, "a_hook.mp4")
run("ffmpeg", "-y", "-ss", "0", "-t", "5", "-i", os.path.join(HERE, "sunrise-room-60s.mp4"), "-an", "-vf", "fps=30,format=yuv420p",
    "-c:v", "libx264", "-crf", "18", a)
parts.append(a)
# B: real footage scenes
for k, (a0, a1, out, text) in enumerate(SCENES, 1):
    cap = os.path.join(S, f"cap{k}.png"); caption_png(text, cap)
    f = out / (a1 - a0)
    clip = os.path.join(S, f"b{k}.mp4")
    run("ffmpeg", "-y", "-ss", str(a0), "-t", str(a1 - a0), "-i", os.path.join(HERE, "screen.mov"), "-i", cap, "-filter_complex",
        f"[0:v]setpts=(PTS-STARTPTS)*{f:.4f},crop=1128:634:232:34,scale=1138:640,fps=30,"
        f"pad={W}:{H}:71:0:color=0x16161c[v];[v][1:v]overlay=0:0,format=yuv420p[o]",
        "-map", "[o]", "-t", str(out), "-an", "-c:v", "libx264", "-crf", "18", clip)
    parts.append(clip)
# C: the rule-change scenes (not in the recording) from the existing replay render, 41-60s
c = os.path.join(S, "c_replay.mp4")
run("ffmpeg", "-y", "-ss", "41", "-t", "19", "-i", os.path.join(HERE, "sunrise-room-60s.mp4"), "-an", "-vf", "fps=30,format=yuv420p",
    "-c:v", "libx264", "-crf", "18", c)
parts.append(c)

lst = os.path.join(S, "list.txt")
with open(lst, "w") as fh:
    for p in parts: fh.write(f"file '{p}'\n")
silent = os.path.join(HERE, "screen_silent.mp4")
run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", silent)
out = os.path.join(HERE, "sunrise-room-60s-screen.mp4")
run("ffmpeg", "-y", "-i", silent, "-i", os.path.join(HERE, "audio", "final_human.m4a"), "-map", "0:v", "-map", "1:a",
    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "copy", "-t", "60", "-movflags", "+faststart", out)
print("built", out)
