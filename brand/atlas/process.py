from PIL import Image
import numpy as np, os

SRC = 'brand/atlas/source/emblem-celestial-primary.png'
OUT_MARKS = 'brand/atlas/marks'
OUT_APP = 'services/web-ui-react/src/brand/assets'
os.makedirs(OUT_MARKS, exist_ok=True); os.makedirs(OUT_APP, exist_ok=True)

def key_alpha(im, lo=10, hi=52):
    """Luminance key: dark bg -> transparent, bright linework -> opaque, soft ramp keeps glow."""
    arr = np.asarray(im.convert('RGB')).astype(np.float32)
    lum = 0.2126*arr[...,0] + 0.7152*arr[...,1] + 0.0722*arr[...,2]
    a = np.clip((lum - lo) / (hi - lo), 0, 1)
    # gamma to retain faint glow but kill pure black
    a = np.power(a, 0.75)
    rgba = np.dstack([arr, (a*255)]).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')

def trim(im, pad=8, athr=10):
    a = np.asarray(im)[...,3]
    ys, xs = np.where(a > athr)
    if len(xs)==0: return im
    x0,x1,y0,y1 = xs.min(),xs.max(),ys.min(),ys.max()
    x0=max(0,x0-pad); y0=max(0,y0-pad); x1=min(im.width,x1+pad); y1=min(im.height,y1+pad)
    return im.crop((x0,y0,x1,y1))

def export(im, name, target_h):
    w = int(im.width * target_h / im.height)
    im2 = im.resize((w, target_h), Image.LANCZOS)
    p_app = os.path.join(OUT_APP, name+'.webp')
    im2.save(p_app, 'WEBP', quality=90, method=6)
    im.save(os.path.join(OUT_MARKS, name+'.png'))
    print(f"{name:16s} master {im.width}x{im.height} -> app {w}x{target_h}  {os.path.getsize(p_app)//1024}KB webp")

src = Image.open(SRC)
W,H = src.size
print('source', W, H)

# emblem-full (whole composition incl. wordmark)
full = trim(key_alpha(src))
export(full, 'emblem-full', 1200)

# emblem-figure: titan + globe + temple, drop the baked wordmark (bottom ~36%)
fig_src = src.crop((0, 0, W, int(H*0.635)))
fig = trim(key_alpha(fig_src))
export(fig, 'emblem-figure', 1080)
