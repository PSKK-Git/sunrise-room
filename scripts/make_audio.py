"""Build voiceover (macOS `say`) + generated background music, mix with ducking, mux onto the silent video."""
import os, subprocess, json

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "audio"); os.makedirs(A, exist_ok=True)
VOICE = "Samantha"
DURS = [5, 4, 5, 3, 7, 3, 7, 2, 5, 3, 4, 2, 4, 6]   # same scene lengths as render.py (sum 60)
LINES = [
    "The owner's at a wedding. A washer just ate a customer's bedsheets.",
    "Staff post the problem in one shared room.",
    "It checks the shop's back office: error E twenty-one.",
    "Then it asks the memory agent I built.",
    "We've seen this before, and the memory knows who said so.",
    "An agent prepares a refund.",
    "But it can't spend money. The refund waits for the owner.",
    "Only the owner approves.",
    "Approved. Applied. And recorded.",
    "Rules change.",
    "Nothing is erased. The old rule stays on record.",
    "So what rested on it?",
    "The memory knows.",
    "Sunrise Room. A real Switch room, a mock shop, and a memory that never overwrites.",
]
starts = [sum(DURS[:i]) for i in range(len(DURS))]

def run(*cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", p], capture_output=True, text=True).stdout
    return float(json.loads(o)["format"]["duration"])

# 1. voice clips, speed up only if a line would overrun its scene
clips = []
for i, (txt, d) in enumerate(zip(LINES, DURS)):
    out = os.path.join(A, f"v{i:02d}.aiff")
    rate = 172
    while True:
        run("say", "-v", VOICE, "-r", str(rate), "-o", out, txt)
        if dur(out) <= d - 0.35 or rate >= 235: break
        rate += 8
    print(f"line {i:02d} rate={rate} len={dur(out):.2f}s / scene {d}s")
    clips.append(out)

# 2. voice track: each clip delayed to its scene start (+0.25s breathing room)
inputs, filt = [], []
for i, c in enumerate(clips):
    inputs += ["-i", c]
    ms = int((starts[i] + (0.5 if i == 0 else 0.25)) * 1000)
    filt.append(f"[{i}:a]aresample=44100,pan=mono|c0=c0,adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(clips)))
filt.append(f"{mix}amix=inputs={len(clips)}:normalize=0,apad=whole_dur=60,atrim=0:60[voice]")
voice = os.path.join(A, "voice.wav")
run("ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[voice]", "-ar", "44100", "-ac", "1", voice)

# 3. generated music: soft pad over a slow I - vi - IV - V loop, plus quiet bell arpeggio. 4 chords x 15s.
chords = [  # Cmaj7, Am7, Fmaj7, G6 (Hz)
    (130.81, 261.63, 329.63, 392.00, 493.88),
    (110.00, 220.00, 261.63, 329.63, 392.00),
    (87.31, 174.61, 220.00, 261.63, 329.63),
    (98.00, 196.00, 246.94, 293.66, 329.63),
]
segs = []
for k, ch in enumerate(chords):
    pad = "+".join(f"0.16*sin(2*PI*{f}*t)+0.07*sin(2*PI*{f*2.003}*t)" for f in ch)
    arp_notes = [ch[1] * 2, ch[2] * 2, ch[3] * 2, ch[2] * 2]
    bells = "+".join(
        f"0.10*exp(-4*mod(t-{n*0.5:.2f}+30,2.0))*sin(2*PI*{f}*t)*gt(mod(t-{n*0.5:.2f}+30,2.0),0)"
        for n, f in enumerate(arp_notes))
    expr = f"(({pad})*0.5*(0.8+0.2*sin(2*PI*0.2*t)))+({bells})"
    out = os.path.join(A, f"m{k}.wav")
    run("ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d=16", "-af", "lowpass=f=2600,volume=0.9", out)
    segs.append(out)
music = os.path.join(A, "music.wav")
cin = [x for s in segs for x in ("-i", s)]
run("ffmpeg", "-y", *cin, "-filter_complex",
    "[0][1]acrossfade=d=1[x1];[x1][2]acrossfade=d=1[x2];[x2][3]acrossfade=d=1[m];"
    "[m]atrim=0:60,afade=t=in:st=0:d=3,afade=t=out:st=55:d=5[mus]", "-map", "[mus]", music)

# 4. duck the music under the voice, balance, loudness-normalise, mux with the video
final_audio = os.path.join(A, "final.m4a")
run("ffmpeg", "-y", "-i", voice, "-i", music, "-filter_complex",
    "[1:a]volume=0.55[mus];[0:a]asplit=2[vo][sc];"
    "[mus][sc]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=500[duck];"
    "[vo][duck]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9[out]",
    "-map", "[out]", "-ar", "44100", "-c:a", "aac", "-b:a", "160k", final_audio)
run("ffmpeg", "-y", "-i", os.path.join(HERE, "sunrise-room-60s.mp4"), "-i", final_audio,
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-t", "60", "-movflags", "+faststart",
    os.path.join(HERE, "sunrise-room-60s-voice.mp4"))
print("done:", dur(os.path.join(HERE, "sunrise-room-60s-voice.mp4")), "seconds")
