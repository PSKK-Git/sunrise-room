"""Render the 60-second Sunrise Room replay from the real room transcript (verbatim, long lines shortened with ...)."""
import os, textwrap
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "frames")
os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
HEL = "/System/Library/Fonts/Helvetica.ttc"
def font(size, bold=False): return ImageFont.truetype(HEL, size, index=1 if bold else 0)

BG, PANEL, TXT, MUTED = (22, 22, 28), (32, 33, 42), (236, 237, 242), (150, 154, 170)
ACCENT, GOOD, WARN = (110, 160, 255), (90, 200, 140), (255, 190, 90)
COL = {"user": (200, 90, 170), "triager": (110, 160, 255), "scribe": (255, 160, 100), "fixer": (170, 130, 255)}

M = {
 1: ("user", False, "@triager Ravi here: washer 3 stopped mid-cycle with a customer's bedsheets inside. Run shopctl machine 3 and tell me the status and error code, then ask @scribe if we've seen this before."),
 2: ("triager", True, "Washer 3 (12kg) is in fault, error code E21 on the display. It stopped mid-cycle and affects order O5001 (2 bedsheets, 4 towels). I'm asking scribe whether E21 has happened before."),
 3: ("triager", True, "@scribe recall E21 washer 3"),
 4: ("scribe", True, "Here is what we know:\n#2 fix: Switching washer 3 off for ten minutes clears E21; if it comes back the same day, call the technician (by Ravi)\n#1 observation: Washer 3 stops with error E21 when the load is over 10kg (by Ravi)"),
 5: ("user", False, "@fixer Washer 3 faulted with Anita's order O5001. Stage a refund for Owner to approve. Do not apply it."),
 6: ("fixer", True, "Refund staged for Owner approval: P1, Rs 180 on order O5001 (Anita Rao). It is not applied. Owner can approve or reject P1."),
 7: ("user", False, "approve"),
 8: ("fixer", True, "Approved and applied: P1 refunded Rs 180 on order O5001 (Anita Rao). The order now shows as refunded and nothing is pending. I recorded the approval under \"owner\"."),
 9: ("user", False, "@scribe replace #4: when a machine faults mid-cycle, stage a refund straight away for regulars (Owner still approves it)"),
 10: ("scribe", True, "#4 is now replaced by #7: when a machine faults mid-cycle, stage a refund straight away for regulars (Owner still approves it) (the old one stays on record)"),
 11: ("user", False, "@scribe blast #3"),
 12: ("scribe", True, "If #3 is wrong, re-check:\n- #4 decision: When a machine faults mid-cycle, offer a free re-wash first ... [replaced by #7]\n- #6 rule: Regular customers get their re-wash free of charge\n- #7 decision: when a machine faults mid-cycle, stage a refund straight away for regulars ..."),
}
LOCAL = {10, 11, 12}  # scribe output run on the same memory locally, not in the room

def wrap(text, f, width):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            t = (cur + " " + word).strip()
            if f.getlength(t) <= width: cur = t
            else: lines.append(cur); cur = word
        lines.append(cur)
    return lines

def rounded(d, box, r, fill): d.rounded_rectangle(box, r, fill=fill)

def chat(shown, caption, new=None, local=False, hi=None):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 64), fill=PANEL)
    d.text((40, 18), "#  sunrise-demo", font=font(28, True), fill=TXT)
    d.text((W - 360, 22), "Switch room  ·  Mattermost", font=font(22), fill=MUTED)
    body = font(25); name = font(24, True)
    # lay out newest at the bottom
    blocks, y_bottom, top_limit = [], 590, 76
    for i in shown:
        who, bot, text = M[i]
        lines = wrap(text, body, 930)
        blocks.append((i, who, bot, lines, 44 + len(lines) * 34 + 14))
    y = y_bottom
    placed = []
    for blk in reversed(blocks):
        y -= blk[4]
        placed.append((y, blk))
    for y, (i, who, bot, lines, h) in placed:
        if y < top_limit - 20: continue
        c = COL[who]
        d.ellipse((50, y + 4, 98, y + 52), fill=c)
        d.text((66, y + 12), who[0].upper(), font=font(26, True), fill=(20, 20, 24))
        d.text((118, y), who, font=name, fill=TXT)
        x = 118 + name.getlength(who) + 12
        if bot:
            rounded(d, (x, y + 3, x + 50, y + 30), 6, (60, 62, 78)); d.text((x + 8, y + 5), "BOT", font=font(17, True), fill=MUTED)
        for k, ln in enumerate(lines):
            ty = y + 40 + k * 34
            fill = TXT
            if hi and any(h in ln for h in hi): fill = WARN
            d.text((118, ty), ln, font=body, fill=fill)
        if i == new:
            d.rectangle((38, y + 2, 42, y + h - 14), fill=c)
    # fade the top edge
    d.rectangle((0, 64, W, 76), fill=BG)
    # caption lower third
    rounded(d, (40, 608, W - 40, 676), 14, (14, 14, 18))
    d.text((64, 624), caption, font=font(30, True), fill=GOOD)
    note = "Scribe output run on the same memory (not typed in this room)" if local else "Replay of the live Switch room run  ·  messages verbatim, long ones shortened (...)  ·  mock shop data"
    d.text((40, 684), note, font=font(17), fill=MUTED)
    return im

def card(lines, sub=None, big=64):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    f = font(big, True); total = len(lines) * (big + 14)
    y = (H - total) // 2 - (20 if sub else 0)
    for ln in lines:
        d.text(((W - f.getlength(ln)) // 2, y), ln, font=f, fill=TXT); y += big + 14
    if sub:
        sf = font(30); d.text(((W - sf.getlength(sub)) // 2, y + 24), sub, font=sf, fill=ACCENT)
    return im

scenes = [
 (card(["The owner is at a wedding.", "A washer just ate a customer's bedsheets."], big=54), 5),
 (chat([1], "Staff post in the room.", new=1), 4),
 (chat([1, 2], "An agent checks the shop's back office.", new=2, hi=["E21", "O5001"]), 5),
 (chat([1, 2, 3], "It asks the memory agent I built.", new=3), 3),
 (chat([1, 2, 3, 4], "Seen it before, and who said so.", new=4, hi=["Ravi", "E21"]), 7),
 (chat([4, 5], "Agents prepare a refund.", new=5), 3),
 (chat([4, 5, 6], "They can't spend money. Not applied yet.", new=6, hi=["not applied", "Not applied"]), 7),
 (chat([5, 6, 7], "Only the owner approves.", new=7), 2),
 (chat([6, 7, 8], "Approved. Applied. Recorded.", new=8, hi=["Approved", "owner"]), 5),
 (chat([8, 9], "Rules change.", new=9, local=True), 3),
 (chat([8, 9, 10], "Nothing is erased. The old rule stays on record.", new=10, local=True, hi=["replaced", "on record"]), 4),
 (chat([9, 10, 11], "What rested on the old rule?", new=11, local=True), 2),
 (chat([10, 11, 12], "The memory knows.", new=12, local=True, hi=["[replaced by #7]"]), 4),
 (card(["Sunrise Room"], sub="Real room. Mock shop. Built on Switch.  github.com/PSKK-Git/sunrise-room", big=84), 6),
]
with open(os.path.join(OUT, "list.txt"), "w") as fh:
    for k, (im, dur) in enumerate(scenes):
        p = os.path.join(OUT, f"s{k:02d}.png"); im.save(p)
        fh.write(f"file '{p}'\nduration {dur}\n")
    fh.write(f"file '{os.path.join(OUT, f's{len(scenes)-1:02d}.png')}'\n")
print("scenes:", len(scenes), "total seconds:", sum(d for _, d in scenes))
