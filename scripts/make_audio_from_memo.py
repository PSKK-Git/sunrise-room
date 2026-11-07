"""Cut a single voice-memo take (14 lines, ~1s pauses between) onto the 60s video, mixed over the generated music.
Usage: python3 human.py /path/to/memo.m4a"""
import os, re, subprocess, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "audio"); os.makedirs(A, exist_ok=True)
DURS = [5, 4, 5, 3, 7, 3, 7, 2, 5, 3, 4, 2, 4, 6]
STARTS = [sum(DURS[:i]) for i in range(len(DURS))]
N = len(DURS)
memo = sys.argv[1]

def run(*cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", p], capture_output=True, text=True).stdout
    return float(json.loads(o)["format"]["duration"])

clean = os.path.join(A, "memo_clean.wav")
run("ffmpeg", "-y", "-i", memo, "-ac", "1", "-ar", "44100", "-af", "highpass=f=80,afftdn=nf=-30", clean)
total = dur(clean)

def segments(noise, d):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", clean, "-af", f"silencedetect=n={noise}dB:d={d}", "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    segs, cur = [], 0.0
    for s, e in zip(starts, ends + [None] * (len(starts) - len(ends))):
        if s - cur > 0.25: segs.append((cur, s))
        cur = e if e is not None else total
    if total - cur > 0.25: segs.append((cur, total))
    return segs

best = None
for noise in (-38, -35, -32, -42, -30):
    for d in (0.6, 0.5, 0.8, 0.4, 1.0):
        s = segments(noise, d)
        if best is None or abs(len(s) - N) < abs(len(best) - N): best = s
        if len(s) == N: break
    if len(best) == N: break
import math
# Raw pieces with short pauses, then group consecutive pieces into N lines so each group's length matches the
# expected spoken length of its line (pauses inside a line, like "Approved. Applied.", are not line breaks).
EXPECT = [3.99, 2.63, 3.38, 2.27, 3.31, 1.92, 3.16, 1.62, 2.52, 1.05, 3.09, 1.40, 1.10, 5.37]
raw = segments(-35, 0.3)
raw = [r for r in raw if r[1] - r[0] > 0.12]
M = len(raw)
k = sum(e - s for s, e in raw) / sum(EXPECT)   # this speaker's pace relative to the reference voice
def gcost(a, b, i):   # group raw[a:b] as line i
    span = raw[b - 1][1] - raw[a][0]
    inner = sum(raw[j + 1][0] - raw[j][1] for j in range(a, b - 1))
    return (math.log(span / (k * EXPECT[i]))) ** 2 + 0.15 * inner
INF = 1e9
dp = [[INF] * (M + 1) for _ in range(N + 1)]; back = [[0] * (M + 1) for _ in range(N + 1)]
dp[0][0] = 0
for i in range(1, N + 1):
    for b in range(i, M + 1):
        for a in range(i - 1, b):
            if dp[i - 1][a] >= INF: continue
            bonus = 0.0
            if a > 0: bonus = 0.6 * math.exp(-3 * (raw[a][0] - raw[a - 1][1]))   # prefer cutting at big pauses
            c = dp[i - 1][a] + gcost(a, b, i - 1) + bonus
            if c < dp[i][b]: dp[i][b] = c; back[i][b] = a
segs, b = [], M
if dp[N][M] < INF:
    for i in range(N, 0, -1):
        a = back[i][b]; segs.append((raw[a][0], raw[b - 1][1])); b = a
    segs.reverse()
else:
    segs = best
print("raw pieces:", M, " pace factor:", round(k, 2))
print(f"found {len(segs)} spoken segments (expected {N})")
if len(segs) != N:
    sys.exit(f"Expected {N} lines but found {len(segs)}. Re-record with clearer 1-second pauses between lines.")

inputs, filt = [], []
for i, (s, e) in enumerate(segs):
    clip = os.path.join(A, f"h{i:02d}.wav")
    s0, e0 = max(0, s - 0.08), min(total, e + 0.12)
    # input-seek (-ss/-t before -i) so the clip's own timeline starts at 0 and the fade times are correct
    run("ffmpeg", "-y", "-ss", str(s0), "-t", str(e0 - s0), "-i", clean, "-af",
        "afade=t=in:d=0.03,afade=t=out:st=%.3f:d=0.06" % max(0, e0 - s0 - 0.06), clip)
    L, room = dur(clip), DURS[i] - 0.15
    tempo = min(1.18, L / room) if L > room else 1.0
    inputs += ["-i", clip]
    ms = int((STARTS[i] + (0.4 if i == 0 else 0.15)) * 1000)
    filt.append(f"[{i}:a]atempo={tempo:.3f},pan=mono|c0=c0,adelay={ms}|{ms}[a{i}]")
    print(f"line {i + 1:02d}: {L:.2f}s in a {DURS[i]}s scene, tempo {tempo:.2f}")
mix = "".join(f"[a{i}]" for i in range(N))
filt.append(f"{mix}amix=inputs={N}:normalize=0,apad=whole_dur=60,atrim=0:60[voice]")
voice = os.path.join(A, "voice_human.wav")
run("ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[voice]", "-ar", "44100", "-ac", "1", voice)

final_audio = os.path.join(A, "final_human.m4a")
run("ffmpeg", "-y", "-i", voice, "-i", os.path.join(A, "music.wav"), "-filter_complex",
    "[1:a]volume=0.5[mus];[0:a]asplit=2[vo][sc];"
    "[mus][sc]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=500[duck];"
    "[vo][duck]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9[out]",
    "-map", "[out]", "-ar", "44100", "-c:a", "aac", "-b:a", "160k", final_audio)
out = os.path.join(HERE, "sunrise-room-60s-human.mp4")
run("ffmpeg", "-y", "-i", os.path.join(HERE, "sunrise-room-60s.mp4"), "-i", final_audio,
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-t", "60", "-movflags", "+faststart", out)
print("done:", out, dur(out), "seconds")
