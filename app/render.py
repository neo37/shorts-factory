"""Build a BusinessPad-dark HyperFrames composition from a storyboard and render it
via OpenMontage. Single-threaded (TZ §4). The videos.ai3d.art footer is permanent;
a demo watermark is added when job.watermark is True.
"""
import html
import json
import logging
import shutil
import subprocess
from pathlib import Path

from config import Config
from . import tts

log = logging.getLogger("videobot.render")

GAP = 0.45


def _ffprobe_dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)]).decode().strip())


def _copy_brand(dst_assets, om_dir):
    """Copy music + logo from an existing project if available (best-effort)."""
    src = om_dir / "projects" / "top-oss-day-bp" / "hyperframes" / "assets"
    (dst_assets / "music").mkdir(parents=True, exist_ok=True)
    (dst_assets / "brand").mkdir(parents=True, exist_ok=True)
    music = src / "music" / "background_music.mp3"
    logo = src / "brand" / "businesspad-logo.svg"
    if music.exists():
        shutil.copy(music, dst_assets / "music" / "background_music.mp3")
    if logo.exists():
        shutil.copy(logo, dst_assets / "brand" / "businesspad-logo.svg")
    return music.exists(), logo.exists()


def _build_vo(scenes, audio_dir, gender):
    """Synthesize per-scene VO, return list of (path, duration). Best-effort (audio optional)."""
    segs = []
    for i, sc in enumerate(scenes):
        vo = (sc.get("vo") or "").strip()
        if not vo:
            segs.append((None, 2.5))
            continue
        out = audio_dir / f"vo_{i}.mp3"
        try:
            tts.synthesize(vo, out, gender=gender, fmt="mp3")
            segs.append((out, _ffprobe_dur(out)))
        except Exception as e:  # noqa: BLE001
            log.warning("scene %d VO failed (%s); using silent hold", i, e)
            segs.append((None, max(2.5, len(vo) / 14)))
    return segs


def _assemble_vo(segs, audio_dir):
    """Concatenate scene VO with GAP silence; loudnorm. Returns (path, total) or (None, computed)."""
    real = [(p, d) for p, d in segs if p]
    if not real:
        return None, sum(d + GAP for _, d in segs) - GAP
    sil = audio_dir / "sil.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", str(GAP), "-q:a", "9", str(sil), "-loglevel", "error"], check=True)
    inputs, order = [], []
    for i, (p, d) in enumerate(segs):
        src = p if p else sil  # silent hold for missing scenes (approx via repeated sil)
        if p:
            inputs += ["-i", str(p)]
            order.append(len(order))
        else:
            # generate a silence of duration d
            spad = audio_dir / f"hold_{i}.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                            "-t", f"{d:.3f}", "-q:a", "9", str(spad), "-loglevel", "error"], check=True)
            inputs += ["-i", str(spad)]
            order.append(len(order))
        inputs += ["-i", str(sil)]
        order.append(len(order))
    order = order[:-1]  # drop trailing gap
    concat = "".join(f"[{i}:a]" for i in order)
    raw = audio_dir / "vo_raw.mp3"
    subprocess.run(["ffmpeg", "-y"] + inputs +
                   ["-filter_complex", f"{concat}concat=n={len(order)}:v=0:a=1[o]",
                    "-map", "[o]", "-ar", "44100", "-b:a", "192k", str(raw), "-loglevel", "error"],
                   check=True)
    final = audio_dir / "vo_full.mp3"
    subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "44100", "-b:a", "192k", str(final), "-loglevel", "error"], check=True)
    return final, _ffprobe_dur(final)


def _esc(s):
    return html.escape(str(s or ""))


def _compose_html(storyboard, segs, total, has_music, has_logo, watermark, footer_url,
                  theme, media_rel=None):
    scenes = storyboard.get("scenes", [])
    media_rel = media_rel or []
    # scene windows
    starts, t = [], 0.0
    for _, d in segs:
        starts.append(t)
        t += d + GAP
    vo_total = t - GAP

    bg_divs, scene_divs, cap_divs, cues = [], [], [], []
    for i, sc in enumerate(scenes):
        s = starts[i]
        d = segs[i][1] + GAP
        # optional user-media background for this scene (image or video), with a dark scrim
        if i < len(media_rel):
            rel = media_rel[i]
            if rel.lower().endswith((".mp4", ".mov", ".webm", ".m4v")):
                bg_divs.append(
                    f'<video class="clip media" src="{rel}" data-start="{s:.3f}" '
                    f'data-duration="{d:.3f}" data-track-index="0" muted></video>'
                    f'<div class="clip scrim" data-start="{s:.3f}" data-duration="{d:.3f}" data-track-index="0"></div>')
            else:
                bg_divs.append(
                    f'<div class="clip mediawrap" data-start="{s:.3f}" data-duration="{d:.3f}" data-track-index="0">'
                    f'<img class="media" src="{rel}"><div class="scrim"></div></div>')
        scene_divs.append(
            f'<div id="s{i}" class="clip stage" data-start="{s:.3f}" data-duration="{d:.3f}" data-track-index="1">'
            f'<div class="eyebrow">{_esc(sc.get("eyebrow"))}</div>'
            f'<h1>{_esc(sc.get("headline"))}</h1></div>')
        cap = _esc(sc.get("caption"))
        cap_divs.append(
            f'<div id="c{i}" class="clip" data-start="{s:.3f}" data-duration="{d:.3f}" data-track-index="3">'
            f'<div class="cap">{cap}</div></div>')
        cues.append(f'tl.from("#s{i} .eyebrow",{{opacity:0,y:16,duration:.4,ease:e}},{s+0.1:.3f});')
        cues.append(f'tl.from("#s{i} h1",{{opacity:0,y:34,duration:.5,ease:e}},{s+0.3:.3f});')
        cues.append(f'tl.from("#c{i} .cap",{{opacity:0,y:14,duration:.35,ease:e}},{s+0.15:.3f});')
        cues.append(f'tl.to("#c{i} .cap",{{opacity:0,duration:.3}},{s+d-0.35:.3f});')

    total = round(max(total, vo_total) + 0.4, 3)
    audio_tags = ('<audio id="vo" src="assets/audio/vo_full.mp3" data-start="0" '
                  f'data-duration="{vo_total:.3f}"></audio>') if any(p for p, _ in segs) else ""
    if has_music:
        audio_tags += (f'\n    <audio id="music" src="assets/music/background_music.mp3" '
                       f'data-start="0" data-duration="{total}" data-volume="0.07"></audio>')
    watermark_div = ('<div class="wm">DEMO · пополни баланс, чтобы убрать</div>' if watermark else "")

    t = theme
    up = "uppercase" if t.get("eyebrow_upper", True) else "none"
    card = (f"border:{t['border']};border-radius:{t['radius']}px;"
            f"box-shadow:{t['shadow']};") if (t.get("border") != "none" or t.get("shadow") != "none") else ""
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>{_esc(storyboard.get('title'))}</title>
<link href="{t['font_url']}" rel="stylesheet">
<style>
:root{{--bg:{t['bg']};--panel:{t['panel']};--primary:{t['primary']};--accent:{t['accent']};--fg:{t['fg']};--fg2:{t['fg2']};--muted:{t['muted']};--font:{t['font_family']};}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font)}}
[data-composition-id="root"]{{position:relative;width:1080px;height:1920px;overflow:hidden;background:var(--bg)}}
.clip{{position:absolute;inset:0}}
.stage{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 110px;text-align:center}}
.media{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.mediawrap{{overflow:hidden}}
.scrim{{position:absolute;inset:0;background:{t['scrim']}}}
.eyebrow{{font-weight:600;font-size:30px;text-transform:{up};letter-spacing:.12em;color:var(--fg2)}}
h1{{font-weight:{t['h1_weight']};letter-spacing:-.02em;font-size:104px;line-height:1.06;margin:26px 0 0;{card}{'padding:30px 44px;background:var(--panel);' if card else ''}}}
.cap{{position:absolute;left:80px;right:80px;bottom:230px;text-align:center;font-weight:700;font-size:50px;line-height:1.25;color:var(--fg)}}
.prog{{position:absolute;left:0;bottom:0;height:8px;background:var(--primary);width:0}}
.footer{{position:absolute;left:0;right:0;bottom:70px;text-align:center;font-weight:600;font-size:30px;color:var(--muted);letter-spacing:.04em}}
.wm{{position:absolute;left:0;right:0;top:80px;text-align:center;font-weight:700;font-size:30px;color:var(--accent);letter-spacing:.12em;text-transform:uppercase}}
</style>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script></head>
<body>
  <div data-composition-id="root" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
    {audio_tags}
    {''.join(bg_divs)}
    {''.join(scene_divs)}
    {''.join(cap_divs)}
    <!-- permanent, non-erasable project footer -->
    <div class="clip" data-start="0" data-duration="{total}" data-track-index="4">
      <div class="footer">{_esc(footer_url)}</div>{watermark_div}
    </div>
    <div class="clip prog" data-start="0" data-duration="{total}" data-track-index="5"></div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{paused:true}}); const e="power2.out";
      tl.fromTo(".prog",{{width:0}},{{width:1080,duration:{total},ease:"none"}},0);
      {''.join(cues)}
      window.__timelines["root"] = tl;
    </script>
  </div>
</body></html>
"""


def render_job(job, storyboard, gender="male"):
    """Full render: VO -> composition -> hyperframes MP4. Returns output path (str)."""
    om = Config.OPENMONTAGE_DIR
    proj = om / "projects" / f"bot-{job.id}"
    hf = proj / "hyperframes"
    audio_dir = hf / "assets" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (hf / "renders").mkdir(parents=True, exist_ok=True)

    has_music, has_logo = _copy_brand(hf / "assets", om)
    # hyperframes.json (registry config) — copy from a known project or write minimal
    ref_cfg = om / "projects" / "top-oss-day-bp" / "hyperframes" / "hyperframes.json"
    if ref_cfg.exists():
        shutil.copy(ref_cfg, hf / "hyperframes.json")
    else:
        (hf / "hyperframes.json").write_text(json.dumps(
            {"paths": {"blocks": "compositions", "assets": "assets"}}))

    # copy user-uploaded media into the render assets, keep scene-order.
    # media_source == "stock" → ignore user media (visuals come from stock/generation).
    media_rel = []
    if job.media_json and (job.media_source or "mix") != "stock":
        um = hf / "assets" / "user_media"
        um.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(json.loads(job.media_json)):
            src = Path(src)
            if not src.exists():
                continue
            dst = um / f"m{i}{src.suffix.lower() or '.bin'}"
            shutil.copy(src, dst)
            media_rel.append(f"assets/user_media/{dst.name}")

    segs = _build_vo(storyboard.get("scenes", []), audio_dir, gender)
    vo_path, vo_total = _assemble_vo(segs, audio_dir)
    if vo_path is None:
        # ensure no dangling audio tag if nothing synthesized
        segs = [(None, d) for _, d in segs]

    # resolve theme: custom theme snapshot on the job wins, else the design_style slug
    from .presets import get_theme
    theme = get_theme(json.loads(job.theme_json)) if job.theme_json else get_theme(job.design_style)

    html_doc = _compose_html(
        storyboard, segs, vo_total, has_music, has_logo,
        watermark=job.watermark, footer_url=Config.PROJECT_FOOTER_URL,
        theme=theme, media_rel=media_rel,
    )
    (hf / "index.html").write_text(html_doc, encoding="utf-8")

    out = hf / "renders" / "final.mp4"
    subprocess.run(
        ["npx", "hyperframes", "render", ".", "-o", "renders/final.mp4",
         "-q", Config.RENDER_QUALITY, "--fps", str(Config.RENDER_FPS)],
        cwd=hf, check=True,
    )
    return str(out)
