"""Conversion des medias vers les formats acceptes par Telegram / WhatsApp.

Gere aussi la forme du sticker (original / carre / rond) et l'ecriture
(watermark) ajoutee en bas a droite.
"""

import logging
import os
import subprocess
import tempfile
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

STICKER_SIZE = 512
VIDEO_MAX_SECONDS = 3
VIDEO_MAX_BYTES = 256 * 1024

SHAPE_ORIGINAL = 'original'
SHAPE_SQUARE = 'square'
SHAPE_ROUND = 'round'

FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
)


def font_path() -> str:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return ''


def _load_font(size: int):
    path = font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


FFMPEG_TIMEOUT = 120


def _run(args):
    try:
        proc = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError('conversion trop longue (délai dépassé)')
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode('utf-8', 'ignore')[-400:])


# --------------------------------------------------------------------------
# helpers image
# --------------------------------------------------------------------------

def _fit_original(im: Image.Image) -> Image.Image:
    ratio = STICKER_SIZE / max(im.width, im.height)
    new_size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
    im = im.resize(new_size, Image.LANCZOS)
    if im.width != STICKER_SIZE and im.height != STICKER_SIZE:
        im = im.resize((STICKER_SIZE, STICKER_SIZE), Image.LANCZOS)
    return im


def _fit_square(im: Image.Image) -> Image.Image:
    """place l'image entiere dans un carre 512x512 transparent"""
    ratio = min(STICKER_SIZE / im.width, STICKER_SIZE / im.height)
    new_size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
    im = im.resize(new_size, Image.LANCZOS)
    canvas = Image.new('RGBA', (STICKER_SIZE, STICKER_SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((STICKER_SIZE - im.width) // 2, (STICKER_SIZE - im.height) // 2), im)
    return canvas


def circle_mask(size: int = STICKER_SIZE) -> Image.Image:
    mask = Image.new('L', (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def _fit_round(im: Image.Image) -> Image.Image:
    """remplit un cercle : on recadre au centre puis on applique un masque rond"""
    ratio = max(STICKER_SIZE / im.width, STICKER_SIZE / im.height)
    im = im.resize(
        (max(1, round(im.width * ratio)), max(1, round(im.height * ratio))), Image.LANCZOS
    )
    left = (im.width - STICKER_SIZE) // 2
    top = (im.height - STICKER_SIZE) // 2
    im = im.crop((left, top, left + STICKER_SIZE, top + STICKER_SIZE))

    mask = circle_mask(STICKER_SIZE)
    out = Image.new('RGBA', (STICKER_SIZE, STICKER_SIZE), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _apply_shape(im: Image.Image, shape: str) -> Image.Image:
    if shape == SHAPE_SQUARE:
        return _fit_square(im)
    if shape == SHAPE_ROUND:
        return _fit_round(im)
    return _fit_original(im)


# ecriture discrete : blanc semi-transparent avec un leger contour
WM_TEXT_ALPHA = 0.45      # 0 = invisible, 1 = opaque
WM_BORDER_ALPHA = 0.25
WM_SIZE_RATIO = 0.065     # taille du texte par rapport a la hauteur


def draw_watermark(im: Image.Image, text: str) -> Image.Image:
    """ecrit le texte en bas a droite du sticker, de facon discrete (transparente)"""
    text = (text or '').strip()
    if not text:
        return im

    im = im.convert('RGBA')
    # on dessine sur un calque separe puis on le fusionne : sinon le texte
    # semi-transparent "trouerait" l'image au lieu de se poser dessus
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = max(14, int(im.height * WM_SIZE_RATIO))
    font = _load_font(size)

    # reduit la police si le texte est trop large
    for _ in range(12):
        box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        if box[2] - box[0] <= im.width * 0.85 or size <= 10:
            break
        size = int(size * 0.88)
        font = _load_font(size)

    stroke = max(1, size // 16)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    margin = max(6, int(im.width * 0.035))
    x = im.width - (box[2] - box[0]) - margin - box[0]
    y = im.height - (box[3] - box[1]) - margin - box[1]
    draw.text(
        (x, y), text, font=font,
        fill=(255, 255, 255, int(255 * WM_TEXT_ALPHA)),
        stroke_width=stroke, stroke_fill=(0, 0, 0, int(255 * WM_BORDER_ALPHA)),
    )
    return Image.alpha_composite(im, layer)


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------

def image_to_webp(data: bytes, shape: str = SHAPE_ORIGINAL, watermark: str = '') -> bytes:
    """transforme une image en sticker statique 512px webp"""
    im = Image.open(BytesIO(data))
    if im.mode != 'RGBA':
        im = im.convert('RGBA')

    im = _apply_shape(im, shape)
    im = draw_watermark(im, watermark)

    out = BytesIO()
    im.save(out, 'WEBP', quality=90, method=6)
    return out.getvalue()


# --------------------------------------------------------------------------
# videos
# --------------------------------------------------------------------------

def _video_filters(tmp: str, shape: str, watermark: str, fps: int) -> list:
    """construit les arguments -filter_complex pour ffmpeg"""
    steps = [f'scale={STICKER_SIZE}:{STICKER_SIZE}:force_original_aspect_ratio=decrease']

    if shape == SHAPE_SQUARE:
        steps.append(
            f'pad={STICKER_SIZE}:{STICKER_SIZE}:(ow-iw)/2:(oh-ih)/2:color=#00000000'
        )
    elif shape == SHAPE_ROUND:
        steps.append(
            f'scale={STICKER_SIZE}:{STICKER_SIZE}:force_original_aspect_ratio=increase'
        )
        steps.append(f'crop={STICKER_SIZE}:{STICKER_SIZE}')

    steps.append(f'fps={fps}')
    steps.append('format=yuva420p')

    inputs = []
    chain = f'[0:v]{",".join(steps)}[v]'
    last = '[v]'

    if shape == SHAPE_ROUND:
        mask_path = os.path.join(tmp, 'mask.png')
        gray = circle_mask(STICKER_SIZE)
        Image.merge('RGB', (gray, gray, gray)).save(mask_path)
        inputs = ['-loop', '1', '-i', mask_path]
        chain += (
            f';[1:v]scale={STICKER_SIZE}:{STICKER_SIZE},format=gray[m]'
            f';[v][m]alphamerge[vm]'
        )
        last = '[vm]'

    text = (watermark or '').strip()
    if text:
        text_path = os.path.join(tmp, 'wm.txt')
        with open(text_path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        fsize = max(18, int(STICKER_SIZE * 0.09))
        fontfile = font_path()
        draw = (
            f"drawtext=textfile='{text_path}'"
            f':fontsize={fsize}:fontcolor=white'
            f':borderw={max(2, fsize // 12)}:bordercolor=black@0.85'
            f':x=w-tw-{int(STICKER_SIZE * 0.03)}:y=h-th-{int(STICKER_SIZE * 0.03)}'
        )
        if fontfile:
            draw += f":fontfile='{fontfile}'"
        chain += f';{last}{draw}[vw]'
        last = '[vw]'

    return inputs, chain, last


def video_to_webm(
    data: bytes,
    suffix: str = '.mp4',
    shape: str = SHAPE_ORIGINAL,
    watermark: str = '',
) -> bytes:
    """convertit une video / GIF en sticker video webm VP9 (512px, 3s max, 30fps)"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in' + suffix)
        dst = os.path.join(tmp, 'out.webm')
        with open(src, 'wb') as fh:
            fh.write(data)

        inputs, chain, last = _video_filters(tmp, shape, watermark, 30)

        out = b''
        for crf in (32, 40, 50):
            _run([
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-t', str(VIDEO_MAX_SECONDS), '-i', src, *inputs,
                '-filter_complex', chain, '-map', last,
                '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', str(crf),
                '-an', '-pix_fmt', 'yuva420p',
                '-f', 'webm', dst,
            ])
            out = open(dst, 'rb').read()
            if len(out) <= VIDEO_MAX_BYTES:
                return out
        return out


def any_to_animated_webp(
    data: bytes,
    suffix: str,
    shape: str = SHAPE_ORIGINAL,
    watermark: str = '',
) -> bytes:
    """convertit une video/webm en webp anime (format attendu par WhatsApp)"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in' + suffix)
        dst = os.path.join(tmp, 'out.webp')
        with open(src, 'wb') as fh:
            fh.write(data)

        inputs, chain, last = _video_filters(tmp, shape, watermark, 15)

        _run([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-t', str(VIDEO_MAX_SECONDS), '-i', src, *inputs,
            '-filter_complex', chain, '-map', last,
            '-loop', '0', '-an', '-fps_mode', 'passthrough',
            '-c:v', 'libwebp', '-quality', '55', '-compression_level', '6',
            dst,
        ])
        return open(dst, 'rb').read()


def to_wa_webp(data: bytes, suffix: str, shape: str = SHAPE_ORIGINAL, watermark: str = '') -> bytes:
    """point d'entree unique pour WhatsApp : renvoie toujours du webp"""
    if suffix in ('.webm', '.mp4', '.gif'):
        return any_to_animated_webp(data, suffix, shape, watermark)
    return image_to_webp(data, shape, watermark)
