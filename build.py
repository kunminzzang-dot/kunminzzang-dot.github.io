#!/usr/bin/env python3
"""Kunminzzang portfolio builder.

content/projects/<code>-<slug>/project.md  + cover.jpg (+cover.mp4) + 01.jpg 02.gif …
src/index.html (home template), src/static/ (copied as is)  ->  dist/

Run:  python3 build.py            (full build into dist/)
"""
import os, re, json, shutil, subprocess, html as H
import yaml
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__)); os.chdir(ROOT)
DIST = 'dist'
MAXW, VIDW = 2000, 1400

# ---------- content ----------
def read_project(folder):
    raw = open(os.path.join(folder, 'project.md'), encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', raw, re.S)
    meta = yaml.safe_load(m.group(1)) or {}
    meta['body'] = [p.strip() for p in m.group(2).strip().split('\n\n') if p.strip()]
    base = os.path.basename(folder); meta['code'], meta['slug'] = base.split('-', 1)
    meta['dir'] = folder
    meta['year'] = str(meta.get('year', ''))
    meta['tags'] = meta.get('tags') or []
    return meta

ALL = [read_project(os.path.join('content/projects', d)) for d in sorted(os.listdir('content/projects'), reverse=True)
       if os.path.exists(os.path.join('content/projects', d, 'project.md'))]
P = [p for p in ALL if p.get('work', True)]
BY = {p['code']: p for p in ALL}

# ---------- media pipeline ----------
def out(path):
    os.makedirs(os.path.dirname(os.path.join(DIST, path)), exist_ok=True); return os.path.join(DIST, path)
def fresh(src, dst): return os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)
def flat(im):
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA'); bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); return bg
    return im.convert('RGB')
def save_jpg(src, dst, maxw):
    if fresh(src, dst): return
    im = Image.open(src)
    if src.lower().endswith('.jpg') and im.width <= maxw: shutil.copy(src, dst); return   # already web-sized: keep bytes untouched
    im = flat(im)
    if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(dst, 'JPEG', quality=86, optimize=True, progressive=True, subsampling=0)
def save_webp(src, dst, maxw, square=False):
    if fresh(src, dst): return
    im = flat(Image.open(src))
    if square:
        s = min(im.size); im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width - s) // 2 + s, (im.height - s) // 2 + s))
    if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(dst, 'WEBP', quality=84, method=4)
def gif_to_mp4(src, dst, maxw):
    if fresh(src, dst): return
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-vf', f"scale='trunc(min({maxw},iw)/2)*2':-2:flags=lanczos,format=yuv420p",
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-movflags', '+faststart', '-an', dst], check=True)
def animated(path):
    try: return getattr(Image.open(path), 'n_frames', 1) > 1
    except Exception: return False
def dims(path):
    with Image.open(path) as im: return im.size

def build_media(p):
    """Returns gallery list of dicts and writes covers. Output names stay g/gCODE-NN.*, tw/CODE-1000.webp, c/CODE.*"""
    code, d = p['code'], p['dir']
    files = sorted(f for f in os.listdir(d) if re.match(r'^\d+\.(jpg|jpeg|png|gif|mp4)$', f, re.I))
    frames = {}
    for f in files: frames.setdefault(f.split('.')[0].zfill(2), []).append(f)
    gal = []
    for k in sorted(frames):
        fs = frames[k]; base = f'g/g{code}-{k}'
        still = next((f for f in fs if not f.lower().endswith(('.mp4', '.gif'))), None)
        gif = next((f for f in fs if f.lower().endswith('.gif')), None)
        mp4 = next((f for f in fs if f.lower().endswith('.mp4')), None)
        if gif and animated(os.path.join(d, gif)):
            gif_to_mp4(os.path.join(d, gif), out(base + '.mp4'), VIDW); save_jpg(os.path.join(d, gif), out(base + '.jpg'), VIDW); kind = 'video'
        elif mp4:
            shutil.copy(os.path.join(d, mp4), out(base + '.mp4'))
            save_jpg(os.path.join(d, still) if still else None, out(base + '.jpg'), MAXW) if still else None; kind = 'video'
        else:
            src = os.path.join(d, still or gif)
            save_jpg(src, out(base + '.jpg'), MAXW); save_webp(out(base + '.jpg'), out(base + '.webp'), MAXW); kind = 'image'
        w, h = dims(out(base + '.jpg')) if os.path.exists(out(base + '.jpg')) else (1600, 1000)
        gal.append(dict(src=base, kind=kind, w=w, h=h))
    cov = os.path.join(d, 'cover.jpg')
    if not os.path.exists(cov):
        cov = next((os.path.join(d, f) for f in ('cover.png', 'cover.gif')), None)
        if cov and not os.path.exists(cov): cov = None
    if cov:
        save_jpg(cov, out(f'c/{code}.jpg'), 1400)
        save_webp(out(f'c/{code}.jpg'), out(f'tw/{code}-1000.webp'), 1000, square=True)
    elif gal:
        save_webp(out(gal[0]['src'] + '.jpg'), out(f'tw/{code}-1000.webp'), 1000, square=True); shutil.copy(out(gal[0]['src'] + '.jpg'), out(f'c/{code}.jpg'))
    cmp4 = os.path.join(d, 'cover.mp4'); cgif = os.path.join(d, 'cover.gif')
    p['cover_mp4'] = None
    if os.path.exists(cmp4): shutil.copy(cmp4, out(f'c/{code}.mp4')); p['cover_mp4'] = f'c/{code}.mp4'
    elif os.path.exists(cgif) and animated(cgif): gif_to_mp4(cgif, out(f'c/{code}.mp4'), 800); p['cover_mp4'] = f'c/{code}.mp4'
    return gal

def shot(g, alt, lazy=True):
    if g['kind'] == 'video':
        return f'<figure class="shot"><video src="{g["src"]}.mp4" poster="{g["src"]}.jpg" autoplay muted loop playsinline preload="metadata" aria-label="{alt}"></video></figure>'
    la = ' loading="lazy"' if lazy else ''
    return (f'<figure class="shot"><picture><source type="image/webp" srcset="{g["src"]}.webp">'
            f'<img src="{g["src"]}.jpg" alt="{alt}" width="{g["w"]}" height="{g["h"]}"{la} decoding="async"></picture></figure>')

ARROW = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 11L11 5M6 5h5v5"/></svg>'

CSS = '''
@font-face{font-family:"Wanted Sans KR";src:url(fonts/WantedSansVariable.woff2) format("woff2-variations"),url(fonts/WantedSansVariable.woff2) format("woff2");font-weight:400 1000;font-display:swap;unicode-range:U+1100-11FF,U+3130-318F,U+A960-A97F,U+AC00-D7A3,U+D7B0-D7FF}
.ko{letter-spacing:-.01em}
:root{--paper:#ffffff;--ink:#0d0d0e;--mute:#7a7b7e;--line:#e3e3e5;--tile:#f1f1f2;
  --sans:"Wanted Sans KR",-apple-system,BlinkMacSystemFont,"SF Pro Text","Apple SD Gothic Neo","Pretendard","Malgun Gothic",system-ui,sans-serif;
  --serif:"Wanted Sans KR","Newsreader","Times New Roman",serif;--display:"Wanted Sans KR","Instrument Serif","Times New Roman",serif;
  --gut:max(20px,env(safe-area-inset-left,0px));--gutR:max(20px,env(safe-area-inset-right,0px));color-scheme:light}
*{box-sizing:border-box}
html,body{margin:0}
:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.45;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
img{display:block;max-width:100%}
.wrap{padding-left:var(--gut);padding-right:var(--gutR)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--paper)}
.hd{position:fixed;top:env(safe-area-inset-top,0px);left:0;right:0;z-index:20;display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding-block:20px;padding-left:var(--gut);padding-right:var(--gutR);mix-blend-mode:difference;color:#fff;font-family:var(--serif);font-weight:500;font-size:19px;letter-spacing:-.02em}
.hd nav{display:flex;gap:28px}
.hd a{transition:opacity .2s}.hd a:hover{opacity:.6}
.hd a[aria-current]{text-decoration:underline;text-underline-offset:5px;text-decoration-thickness:1px}
a:focus-visible{outline:2px solid var(--ink);outline-offset:3px}

.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.card{position:relative;display:block;aspect-ratio:1/1;border-radius:10px;overflow:hidden;background:var(--tile);isolation:isolate}
.card img,.card video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .9s cubic-bezier(.2,.7,.2,1)}
.card::before,.card::after{content:"";position:absolute;left:0;right:0;z-index:1;pointer-events:none}
.card::before{top:0;height:30%;background:linear-gradient(rgba(0,0,0,.42),transparent)}
.card::after{bottom:0;height:26%;background:linear-gradient(transparent,rgba(0,0,0,.38))}
.card:hover img,.card:hover video{transform:scale(1.035)}
.card .top{position:absolute;z-index:2;top:0;left:0;right:0;display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:20px 22px;color:#fff}
.card h2,.card h3{margin:0;font-family:var(--serif);font-weight:500;font-size:clamp(19px,1.7vw,24px);letter-spacing:-.02em;line-height:1.15}
.card .go{flex:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:rgba(255,255,255,.22);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);transition:background .3s,color .3s,transform .4s cubic-bezier(.2,1.4,.4,1)}
.card .go svg{width:15px;height:15px}
.card:hover .go{background:#fff;color:var(--ink);transform:rotate(45deg)}
.card .tags{position:absolute;z-index:2;left:22px;bottom:20px;right:22px;display:flex;flex-wrap:wrap;gap:6px}
.card .tags span{font-size:11px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#fff;padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.18);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);font-variant-numeric:tabular-nums}
.card .tags .yr{background:rgba(0,0,0,.35)}
.card video{opacity:0;transition:opacity .4s,transform .9s cubic-bezier(.2,.7,.2,1)}.card video.on{opacity:1}

.foot{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) minmax(0,1.4fr);gap:24px;padding-block:120px 28px}
.foot h5{margin:0 0 14px;font-size:12px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)}
.foot ul{list-style:none;margin:0;padding:0;line-height:1.75}
.foot a:hover{opacity:.6}
.foot .mail{font-family:var(--serif);font-weight:500;font-size:clamp(22px,2.2vw,32px);letter-spacing:-.02em;line-height:1.1;user-select:all;word-break:break-all}
.legal{display:flex;justify-content:space-between;gap:12px;color:var(--mute);font-size:13px;padding-block:0 max(20px,env(safe-area-inset-bottom,0px))}
@media (max-width:820px){.grid{grid-template-columns:1fr}.foot{grid-template-columns:1fr 1fr}.foot>div:last-child{grid-column:1/-1}.hd{font-size:17px}.hd nav{gap:16px}}
@media (prefers-reduced-motion:reduce){.card img,.card .go{transition:none}}
'''

def head(title, extra=''):
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{H.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Instrument+Serif&display=swap" rel="stylesheet">
<style>{CSS}{extra}</style>
</head>
<body>
<header class="hd">
  <a href="./">Kunminzzang</a>
  <nav aria-label="주 메뉴">
    <a href="work.html"{' aria-current="page"' if title.startswith('Work') else ''}>Work({len(P)})</a>
    <a href="./#about">About</a>
    <a href="#contact">Contact</a>
  </nav>
</header>
'''

FOOT = '''<script>
(function(){
  const io='IntersectionObserver' in window?new IntersectionObserver(es=>es.forEach(e=>{const v=e.target;
    if(e.isIntersecting){if(!v.src&&v.dataset.src){v.src=v.dataset.src;v.addEventListener('playing',()=>v.classList.add('on'),{once:true});}v.play&&v.play().catch(()=>{});}
    else if(v.src)v.pause();}),{rootMargin:'300px 0px'}):null;
  window.__vids=root=>root.querySelectorAll('video[data-src]').forEach(v=>{if(io)io.observe(v);else{v.src=v.dataset.src;v.classList.add('on');}});
  window.__vids(document);
})();
</script>
<script>
// Hangul runs get Wanted Sans (via unicode-range) and their own -10 tracking
(function(){
  const re=/[ᄀ-ᇿ㄰-㆏가-힣]+(?:[\\s?!.,·…~'’"“”()-]*[ᄀ-ᇿ㄰-㆏가-힣]+)*/g;
  function wrap(root){window.__ko=window.__ko||wrap;
    const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{const p=n.parentNode;if(!p||/^(SCRIPT|STYLE|TEXTAREA|TITLE)$/.test(p.nodeName)||p.closest&&(p.closest('svg')||p.closest('.ko')))return NodeFilter.FILTER_REJECT;re.lastIndex=0;return re.test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_SKIP;}});
    const list=[];while(w.nextNode())list.push(w.currentNode);
    list.forEach(n=>{const t=n.nodeValue,f=document.createDocumentFragment();let last=0;re.lastIndex=0;let m;
      while((m=re.exec(t))){if(m.index>last)f.appendChild(document.createTextNode(t.slice(last,m.index)));const s=document.createElement('span');s.className='ko';s.textContent=m[0];f.appendChild(s);last=m.index+m[0].length;}
      if(last<t.length)f.appendChild(document.createTextNode(t.slice(last)));n.parentNode.replaceChild(f,n);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>wrap(document.body));else wrap(document.body);
})();
</script>
<footer class="wrap" id="contact">
  <div class="foot">
    <div><h5>Socials</h5><ul>
      <li><a href="https://www.instagram.com/kkunminzzang/" target="_blank" rel="noopener">Instagram</a></li>
      <li><a href="https://www.behance.net/kunminlee" target="_blank" rel="noopener">Behance</a></li>
      <li><a href="https://www.youtube.com/channel/UCegYtwkw9P16WzFgJvIMKrg" target="_blank" rel="noopener">YouTube</a></li>
      <li><a href="https://blog.naver.com/kunminzzzang" target="_blank" rel="noopener">Blog</a></li>
      <li><a href="https://dingbatfont.netlify.app/" target="_blank" rel="noopener">Dingbat Font</a></li>
      <li><a href="https://noonnu.cc/font_page/1956" target="_blank" rel="noopener">Noonnu</a></li></ul></div>
    <div><h5>Menu</h5><ul><li><a href="./">Home</a></li><li><a href="work.html">Work</a></li><li><a href="./#about">About</a></li></ul></div>
    <div></div>
    <div><h5>Contact</h5><div class="mail">kunminzzang@gmail.com</div></div>
  </div>
  <div class="legal"><span>© 2026 이근민</span><a href="#top">Back to top ↑</a></div>
</footer>
</body>
</html>
'''


def media(p):
    n, code = p['title'], p['code']
    img = f'<img src="tw/{code}-1000.webp" alt="{H.escape(n)}" width="1000" height="1000" loading="lazy" decoding="async">'
    if p.get('cover_mp4'):
        return img + f'<video data-src="{p["cover_mp4"]}" muted loop playsinline preload="none" aria-hidden="true"></video>'
    return img

def card(p, tag='h2'):
    t = ''.join(f'<span>{x}</span>' for x in p['tags'])
    return f'''      <a class="card" href="p-{p['slug']}.html">
        {media(p)}
        <div class="top"><{tag}>{H.escape(p['title'])}</{tag}><span class="go" aria-hidden="true">{ARROW}</span></div>
        <div class="tags"><span class="yr">{p['year']}</span>{t}</div>
      </a>
'''

def ov(p):
    out_ = ''.join(f'        <p>{H.escape(x)}</p>\n' for x in p['body'])
    if p.get('results'):
        out_ += '        <ul class="res">' + ''.join(f'<li>{H.escape(x)}</li>' for x in p['results']) + '</ul>\n'
    rows = [('Client', p.get('client')), ('Role', p.get('role')), ('Team', p.get('team')),
            ('Services', ' / '.join(p['tags'])), ('Period', p.get('period') or p['year'])]
    out_ += '        <dl class="meta">\n' + ''.join(f'          <div><dt>{k}</dt><dd>{H.escape(str(v))}</dd></div>\n' for k, v in rows if v) + '        </dl>\n'
    return out_

DETAIL_CSS = '''
.ttl-row{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;padding-block:120px 40px}
.ttl-meta{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;flex:none;max-width:40%;padding-bottom:.5em}
.ttl-meta span{font-size:12px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;padding:6px 11px;border-radius:999px;border:1px solid var(--line);color:#3f4043;font-variant-numeric:tabular-nums}
.ttl-meta span:first-child{background:var(--ink);border-color:var(--ink);color:#fff}
.ttl{margin:0;text-align:left;font-family:var(--display);font-weight:400;font-size:clamp(56px,9vw,150px);line-height:.92;letter-spacing:-.02em;text-wrap:balance}
.shot{margin:0 0 12px;border-radius:10px;overflow:hidden;background:var(--tile)}
.shot img,.shot video{display:block;width:100%;height:auto}
.ov{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:24px;margin:0 0 12px;padding:clamp(24px,3vw,40px);border-radius:10px;background:var(--tile)}
.ov .lb{font-size:12px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)}
.ov .txt p{margin:0 0 1em;max-width:58ch;font-size:16px;line-height:1.6;color:#3f4043}
.meta{margin:28px 0 0;max-width:58ch;border-top:1px solid var(--line)}
.meta div{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-bottom:1px solid var(--line)}
.meta dt{color:var(--mute)}
.meta dd{margin:0;font-size:13px;font-weight:500;letter-spacing:.02em;text-align:right;max-width:70%}
.res{list-style:none;margin:6px 0 0;padding:0;max-width:58ch;display:grid;gap:8px}
.res li{position:relative;padding-left:18px;font-size:15px;line-height:1.5;color:var(--ink)}
.res li::before{content:"";position:absolute;left:0;top:.62em;width:8px;height:1px;background:var(--ink)}
.more{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;padding-block:100px 24px}
.more h2{margin:0;font-family:var(--serif);font-weight:500;font-size:clamp(32px,3.6vw,52px);letter-spacing:-.02em;line-height:1}
.pill{display:inline-flex;align-items:center;border:1px solid var(--ink);border-radius:999px;padding:10px 18px;font-size:14px;font-weight:500;transition:background .25s,color .25s}
.pill:hover{background:var(--ink);color:var(--paper)}
@media (max-width:820px){.ov{grid-template-columns:1fr}.ttl-row{padding-block:104px 28px;flex-direction:column;align-items:flex-start;gap:16px}.ttl-meta{justify-content:flex-start;max-width:none;padding:0}}
'''
# ---- work.html
WORK_CSS = DETAIL_CSS + '''
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g3 .card .top{padding:16px 18px}.g3 .card .tags{left:18px;bottom:16px;right:18px}
.g3 .card h2{font-size:clamp(18px,1.45vw,22px)}
@media (max-width:1100px){.g3{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:820px){.g3{grid-template-columns:1fr}}

/* project sheet */
html.sheet-open{overflow:hidden}
body{transition:background .6s}
html.sheet-open body{background:#0e0e10}
.page{transform-origin:50% 0;transition:transform .7s cubic-bezier(.32,.72,0,1),border-radius .7s,filter .7s;background:var(--paper)}
html.sheet-open .page{transform:translateY(14px) scale(.955);border-radius:16px;overflow:hidden;filter:brightness(.8) blur(10px)}
html.sheet-open .hd{opacity:0;pointer-events:none}
.hd{transition:opacity .4s}
.sh-bg{position:fixed;inset:0;z-index:40;background:rgba(8,8,10,.14);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);opacity:0;pointer-events:none;transition:opacity .6s}
html.sheet-open .sh-bg{opacity:1;pointer-events:auto;cursor:zoom-out}
.sheet{position:fixed;z-index:50;left:200px;right:200px;bottom:0;top:max(30px,env(safe-area-inset-top,0px));background:var(--paper);border-radius:18px 18px 0 0;
  transform:translateY(102%);transition:transform .75s cubic-bezier(.32,.72,0,1);overflow:hidden;display:flex;flex-direction:column;box-shadow:0 -20px 60px rgba(0,0,0,.18)}
html.sheet-open .sheet{transform:none}
.sheet[hidden]{display:none}
.sheet.drag{transition:none}
.sh-bar{flex:none;position:relative;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px var(--gutR) 12px var(--gut);border-bottom:1px solid transparent;transition:border-color .3s;touch-action:none;cursor:grab}
.sheet.scrolled .sh-bar{border-color:var(--line)}
.sh-bar::before{content:"";position:absolute;left:50%;top:7px;width:38px;height:4px;margin-left:-19px;border-radius:2px;background:#d6d6d9}
.sh-t{display:flex;align-items:baseline;gap:12px;min-width:0;font-family:var(--serif);font-weight:500;font-size:17px;letter-spacing:-.02em;opacity:0;transform:translateY(4px);transition:opacity .35s,transform .35s}
.sheet .sh-t{opacity:1;transform:none}
.sh-t i{font-style:normal;font-family:var(--sans);font-size:12px;color:var(--mute);font-variant-numeric:tabular-nums;letter-spacing:.04em}
.sh-t b{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sh-ctl{display:flex;gap:6px;flex:none}
.sh-btn{all:unset;cursor:pointer;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;border:1px solid var(--line);background:var(--paper);transition:background .2s,border-color .2s,color .2s}
.sh-btn:hover{background:var(--ink);border-color:var(--ink);color:#fff}
.sh-btn:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.sh-btn svg{width:14px;height:14px}
.sh-body{flex:1;overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
.sh-in{opacity:0;transform:translateY(18px);transition:opacity .5s ease,transform .7s cubic-bezier(.22,1,.36,1)}
.sh-in.on{opacity:1;transform:none}
.sh-body .ttl-row{display:none}.sh-body .sh-in{padding-top:4px}
.sh-body .more .pill{display:none}
.sh-load{position:absolute;left:50%;top:50%;width:22px;height:22px;margin:-11px;border-radius:50%;border:1.5px solid var(--line);border-top-color:#FF5CB0;animation:shspin .8s linear infinite;opacity:0;transition:opacity .2s}
.sheet.loading .sh-load{opacity:1}
@keyframes shspin{to{transform:rotate(360deg)}}
@media (max-width:1100px){.sheet{left:40px;right:40px}}
@media (max-width:820px){.sheet{left:0;right:0}}
@media (prefers-reduced-motion:reduce){.page,.sheet,.sh-in{transition:none}}
.intro{position:relative}
.orb{position:absolute;pointer-events:none;opacity:0;transition:opacity 1.2s ease}
.orb.on{opacity:1}
.orb canvas{display:block;width:100%;height:100%}
.intro{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);align-items:end;gap:24px;padding-block:120px 56px}
.intro h1{margin:0;font-family:var(--display);font-weight:400;font-size:clamp(68px,11vw,176px);line-height:.88;letter-spacing:-.02em}
.intro p{margin:0 0 .6em;max-width:30ch;justify-self:end;font-size:clamp(17px,1.6vw,23px);line-height:1.35;letter-spacing:-.01em;color:var(--mute)}
.intro p b{color:var(--ink);font-weight:500}
@media (max-width:820px){.intro{grid-template-columns:1fr;padding-block:104px 32px}.intro p{justify-self:start}}
'''
orb_js = r'''<script>
history.scrollRestoration='manual';scrollTo(0,0);
document.querySelectorAll('a[href="work.html"]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();scrollTo({top:0,behavior:'smooth'});}));
function initOrb(){
  if(!window.THREE)return;
  const intro=document.querySelector('.intro'),h1=intro.querySelector('h1'),p=intro.querySelector('p');
  const box=document.createElement('div');box.className='orb';box.setAttribute('aria-hidden','true');intro.appendChild(box);
  const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));box.appendChild(renderer.domElement);
  const scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(35,1,.1,100);cam.position.z=3.5;
  const N=1600,pos=new Float32Array(N*3),rnd=new Float32Array(N);
  for(let i=0;i<N;i++){const y=1-(i+.5)/N*2,r=Math.sqrt(1-y*y),t=i*2.399963;const j=1+(Math.random()-.5)*.04;pos[i*3]=Math.cos(t)*r*j;pos[i*3+1]=y*j;pos[i*3+2]=Math.sin(t)*r*j;rnd[i]=Math.random();}
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(pos,3));geo.setAttribute('aRand',new THREE.BufferAttribute(rnd,1));
  const mat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{uTime:{value:0},uPR:{value:renderer.getPixelRatio()},uSize:{value:1}},
    vertexShader:`attribute float aRand;uniform float uTime,uPR,uSize;varying float vA;
      void main(){vec3 p=position*(1.+.015*sin(uTime*1.3+aRand*40.));vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;
        float lit=.5+.5*dot(normalize(position),normalize(vec3(-.45,.7,.55)));float front=smoothstep(-1.2,1.,(modelViewMatrix*vec4(position,0.)).z);
        vA=(.55+.45*sin(uTime*(1.4+aRand*2.)+aRand*60.))*mix(.25,1.,lit)*mix(.35,1.,front);
        gl_PointSize=uSize*(1.1+aRand*1.3)*uPR*(3.5/-mv.z);}`,
    fragmentShader:`varying float vA;void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;vec3 col=mix(vec3(.04,.04,.045),vec3(.42,.42,.45),smoothstep(.35,1.,vA));gl_FragColor=vec4(col,smoothstep(.5,.3,d)*(.35+.6*vA));}`});
  const pts=new THREE.Points(geo,mat);pts.rotation.x=.35;scene.add(pts);
  let size=0;
  function place(){
    const ir=intro.getBoundingClientRect(),hr=h1.getBoundingClientRect(),pr=p.getBoundingClientRect(),cs=getComputedStyle(intro);
    const mobile=innerWidth<=820;
    const avail=mobile?hr.height*.62:(pr.top-hr.top-28);
    size=Math.round(Math.max(90,Math.min(mobile?130:230,avail)));
    box.style.width=box.style.height=size+'px';
    box.style.top=(hr.top-ir.top)+'px';
    box.style.right=cs.paddingRight;
    renderer.setSize(size,size,false);mat.uniforms.uSize.value=size/150;
  }
  place();addEventListener('resize',place);if(document.fonts)document.fonts.ready.then(place);
  let tx=0,ty=0,mx=0,my=0;addEventListener('pointermove',e=>{tx=(e.clientX/innerWidth-.5)*.5;ty=(e.clientY/innerHeight-.5)*.35;});
  let vis=true;new IntersectionObserver(es=>{vis=es[0].isIntersecting}).observe(box);
  const t0=performance.now();
  (function loop(){requestAnimationFrame(loop);if(!vis)return;const t=(performance.now()-t0)/1000;mat.uniforms.uTime.value=t;
    mx+=(tx-mx)*.05;my+=(ty-my)*.05;pts.rotation.y=(reduce?0:t*.18)+mx;pts.rotation.x=.35+my;renderer.render(scene,cam);})();
  requestAnimationFrame(()=>box.classList.add('on'));
}
function loadThree(){const t=document.createElement('script');t.src='https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';t.onload=initOrb;document.head.appendChild(t);}
if(document.readyState==='complete')setTimeout(loadThree,0);else addEventListener('load',()=>setTimeout(loadThree,0));
</script>
'''
sheet_js = r'''<div class="sh-bg" aria-hidden="true"></div>
<div class="sheet" role="dialog" aria-modal="true" aria-label="프로젝트" hidden>
  <div class="sh-bar">
    <div class="sh-t"><i id="shN">01 / 23</i><b id="shT"></b></div>
    <div class="sh-ctl">
      <button class="sh-btn" id="shPrev" type="button" aria-label="이전 프로젝트"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M13 8H3M7 4L3 8l4 4"/></svg></button>
      <button class="sh-btn" id="shNext" type="button" aria-label="다음 프로젝트"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
      <button class="sh-btn" id="shX" type="button" aria-label="닫기"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg></button>
    </div>
  </div>
  <div class="sh-body" id="shBody"></div>
  <span class="sh-load" aria-hidden="true"></span>
</div>
<script>
(function(){
  const root=document.documentElement,sheet=document.querySelector('.sheet'),bg=document.querySelector('.sh-bg'),body=document.getElementById('shBody');
  const links=[...document.querySelectorAll('.grid .card')].map(a=>a.getAttribute('href'));
  const cache={};let cur=-1,lastFocus=null,token=0;
  const get=h=>cache[h]||(cache[h]=fetch(h).then(r=>r.text()).then(t=>{const d=new DOMParser().parseFromString(t,'text/html');const m=d.querySelector('main');m.querySelectorAll('.more .pill').forEach(x=>x.remove());return {html:m.innerHTML,title:(d.querySelector('.ttl')||{}).textContent||''};}));
  document.querySelectorAll('.grid .card').forEach(a=>a.addEventListener('pointerenter',()=>get(a.getAttribute('href')),{once:true}));
  function show(h,push){
    const i=links.indexOf(h);cur=i;const my=++token;
    sheet.classList.add('loading');
    const inner=body.querySelector('.sh-in');if(inner)inner.classList.remove('on');
    const t0=performance.now();
    get(h).then(d=>{if(my!==token)return;setTimeout(()=>{if(my!==token)return;
      body.innerHTML='<div class="sh-in">'+d.html+'</div>';body.scrollTop=0;sheet.classList.remove('scrolled','loading');
      if(window.__ko)window.__ko(body);
      body.querySelectorAll('video:not([data-src])').forEach(v=>{v.muted=true;v.play&&v.play().catch(()=>{});});if(window.__vids)window.__vids(body);
      document.getElementById('shT').textContent=d.title;document.getElementById('shN').textContent=String(i+1).padStart(2,'0')+' / '+links.length;
      requestAnimationFrame(()=>requestAnimationFrame(()=>body.querySelector('.sh-in').classList.add('on')));
    },Math.max(0,(inner?260:120)-(performance.now()-t0)));}).catch(()=>{location.href=h;});
    if(push)history.pushState({sheet:h},'','#'+h.replace(/\.html$/,''));else history.replaceState({sheet:h},'','#'+h.replace(/\.html$/,''));
  }
  function open(h){
    lastFocus=document.activeElement;sheet.hidden=false;
    const sw=innerWidth-root.clientWidth;root.style.paddingRight=sw?sw+'px':'';
    void sheet.offsetHeight;requestAnimationFrame(()=>{root.classList.add('sheet-open');});
    show(h,true);setTimeout(()=>document.getElementById('shX').focus({preventScroll:true}),400);
  }
  function close(fromPop){
    if(!root.classList.contains('sheet-open'))return;token++;
    root.classList.remove('sheet-open');sheet.style.transform='';
    setTimeout(()=>{if(!root.classList.contains('sheet-open')){sheet.hidden=true;body.innerHTML='';root.style.paddingRight='';}},760);
    if(!fromPop&&history.state&&history.state.sheet)history.back();
    if(lastFocus)lastFocus.focus({preventScroll:true});
  }
  document.addEventListener('click',e=>{
    const a=e.target.closest('a.card');if(!a||e.metaKey||e.ctrlKey||e.shiftKey)return;
    const h=a.getAttribute('href');if(!/^p-.*\.html$/.test(h))return;e.preventDefault();
    if(root.classList.contains('sheet-open'))show(h,false);else open(h);
  });
  bg.addEventListener('click',()=>close());
  document.getElementById('shX').addEventListener('click',()=>close());
  document.getElementById('shPrev').addEventListener('click',()=>show(links[(cur-1+links.length)%links.length],false));
  document.getElementById('shNext').addEventListener('click',()=>show(links[(cur+1)%links.length],false));
  addEventListener('keydown',e=>{if(!root.classList.contains('sheet-open'))return;if(e.key==='Escape')close();if(e.key==='ArrowRight'&&!e.target.closest('input,textarea'))document.getElementById('shNext').click();if(e.key==='ArrowLeft')document.getElementById('shPrev').click();});
  addEventListener('popstate',e=>{if(e.state&&e.state.sheet){if(!root.classList.contains('sheet-open'))open(e.state.sheet);else show(e.state.sheet,false);}else close(true);});
  body.addEventListener('scroll',()=>sheet.classList.toggle('scrolled',body.scrollTop>40),{passive:true});
  // drag the bar down to dismiss
  const bar=sheet.querySelector('.sh-bar');let y0=null,dy=0;
  bar.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;y0=e.clientY;dy=0;sheet.classList.add('drag');bar.setPointerCapture(e.pointerId);});
  bar.addEventListener('pointermove',e=>{if(y0===null)return;dy=Math.max(0,e.clientY-y0);sheet.style.transform='translateY('+dy+'px)';});
  const end=()=>{if(y0===null)return;y0=null;sheet.classList.remove('drag');if(dy>120)close();else sheet.style.transform='';};
  bar.addEventListener('pointerup',end);bar.addEventListener('pointercancel',end);
  const m=location.hash.match(/^#(p-[\w-]+)$/);if(m&&links.includes(m[1]+'.html'))open(m[1]+'.html');
})();
</script>
'''

if os.path.exists(DIST):
    for f in os.listdir(DIST):
        if f.endswith('.html'): os.remove(os.path.join(DIST, f))
os.makedirs(DIST, exist_ok=True)
GAL = {}
for p in ALL: GAL[p['code']] = build_media(p)

work = head('Work — Kunminzzang', WORK_CSS) + f'''<div class="page"><main id="top">
  <section class="intro wrap" aria-labelledby="t">
    <h1 id="t">Selected<br>Work</h1>
    <p>A <b>curated</b> collection of projects across <b>branding</b>, packaging, <b>type</b> and contents, 2015 to now.</p>
  </section>
  <section class="grid g3 wrap" aria-label="프로젝트 목록">
{''.join(card(p) for p in P)}  </section>
</main>
'''+ orb_js + FOOT.replace('</footer>','</footer></div>'+sheet_js,1)
open(os.path.join(DIST, 'work.html'), 'w').write(work)

# ---------- detail pages ----------
for i, p in enumerate(P):
    n = p['title']; imgs = GAL[p['code']]
    cov, rest = imgs[0], imgs[1:]
    nxt = [P[(i + 1) % len(P)], P[(i + 2) % len(P)]]
    shots = ''.join('    ' + shot(g, f'{H.escape(n)} {k+2}') + '\n' for k, g in enumerate(rest))
    page = head(f'{n} — Kunminzzang', DETAIL_CSS) + f'''<main id="top">
  <div class="ttl-row wrap"><h1 class="ttl">{H.escape(n)}</h1><div class="ttl-meta"><span>{p['year']}</span>{''.join(f'<span>{t}</span>' for t in p['tags'])}</div></div>
  <div class="wrap">
    {shot(cov, H.escape(n) + ' 대표 이미지', False)}
    <section class="ov" aria-label="Overview">
      <div class="lb">(Overview)</div>
      <div class="txt">
{ov(p)}      </div>
    </section>
{shots}  </div>
  <div class="more wrap"><h2>More projects</h2><a class="pill" href="work.html">View all</a></div>
  <section class="grid wrap" aria-label="다른 프로젝트">
{''.join(card(q, 'h3') for q in nxt)}  </section>
</main>
''' + FOOT
    open(os.path.join(DIST, f'p-{p["slug"]}.html'), 'w').write(page)

# ---------- home: featured rail from project.md "featured:" ----------
PLUS = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M7 1v12M1 7h12"/></svg>'
feats = sorted([p for p in ALL if p.get('featured')], key=lambda p: p['featured']['order'])
cards = []
for i, p in enumerate(feats, 1):
    f = p['featured']; t = f.get('title', p['title']); code = p['code']
    medium = (f'<video src="{p["cover_mp4"]}" poster="c/{code}.jpg" autoplay muted loop playsinline preload="metadata" aria-label="{H.escape(t)}"></video>'
              if p.get('cover_mp4') else f'<img src="c/{code}.jpg" alt="{H.escape(t)} — {H.escape(f["meta"])}" loading="lazy">')
    if p.get('work', True): links = f'<a href="p-{p["slug"]}.html" tabindex="-1">프로젝트 보기</a>'
    else: links = '<div class="lnks">' + ''.join(f'<a href="{l["url"]}" target="_blank" rel="noopener" tabindex="-1">{H.escape(l["label"])}</a>' for l in p.get('links', [])) + '</div>'
    cards.append(f'''      <article class="fw-card" id="fw-{i}" style="--story:{f.get('color', 'var(--tile)')}">
        <div class="fw-media">
          {medium}
          <div class="fw-story" aria-hidden="true">
            <div class="meta">{H.escape(f['meta'])}</div>
            <p>{H.escape(f['text'])}</p>
            {links}
          </div>
          <button class="fw-plus" type="button" aria-expanded="false" aria-controls="fw-{i}" aria-label="{H.escape(t)} 소개 열기">{PLUS}</button>
        </div>
        <div class="fw-info"><div><h3>{H.escape(t)}</h3><div class="sub">{H.escape(f['meta'])}</div></div></div>
      </article>
''')
home = open('src/index.html', encoding='utf-8').read()
home = (home.replace('<!--FEATURED-->', ''.join(cards)).replace('{{FEATURED_COUNT}}', f'{len(feats):02d}')
            .replace('{{FEATURED_BAR}}', '<i></i>' * len(feats)))
open(os.path.join(DIST, 'index.html'), 'w').write(home)

# ---------- static files ----------
for r, _, fs in os.walk('src/static'):
    for f in fs:
        s_ = os.path.join(r, f); d_ = out(os.path.relpath(s_, 'src/static'))
        if not fresh(s_, d_): shutil.copy(s_, d_)
print(f'built {len(P)} projects, {len(feats)} featured -> {DIST}/')
