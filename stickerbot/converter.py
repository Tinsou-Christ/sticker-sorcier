"""Conversion des medias vers les formats acceptes par Telegram / WhatsApp.

Gere aussi la forme du sticker (original / carre / rond) et l'ecriture
(watermark) ajoutee en bas a gauche.
"""

import logging
import os
import subprocess
import tempfile
from io import BytesIO

from PIL import Image, ImageDraw
from text_renderer import DEFAULT_COLOR, render_text

logger = logging.getLogger(__name__)

STICKER_SIZE = 512
VIDEO_MAX_SECONDS = 3
VIDEO_MAX_BYTES = 256 * 1024

SHAPE_ORIGINAL = 'original'
SHAPE_SQUARE = 'square'
SHAPE_ROUND = 'round'

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


def _wm_margin(width: int, shape: str) -> int:
    """en rond, le coin est hors du cercle : on rentre l'ecriture dans le disque"""
    if shape == SHAPE_ROUND:
        return int(width * 0.17)
    return max(6, int(width * 0.035))


def watermark_layer(width, height, text, shape, color=DEFAULT_COLOR):
    layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    if not (text or '').strip():
        return layer
    margin = _wm_margin(width, shape)
    max_width = width - 2 * margin
    # Keep the whole label inside the lower-left part of a circular sticker.
    if shape == SHAPE_ROUND:
        max_width = int(width * 0.55)
    label = render_text(text.strip(), max_width, max(12, height // 5),
                        max(14, int(height * WM_SIZE_RATIO)), color)
    layer.alpha_composite(label, (margin, height - margin - label.height))
    return layer


def draw_watermark(im: Image.Image, text: str, shape: str = SHAPE_ORIGINAL,
                   color: str = DEFAULT_COLOR) -> Image.Image:
    if not (text or '').strip():
        return im
    im = im.convert('RGBA')
    return Image.alpha_composite(im, watermark_layer(im.width, im.height, text, shape, color))


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------

def image_to_webp(data: bytes, shape: str = SHAPE_ORIGINAL, watermark: str = '', color: str = DEFAULT_COLOR) -> bytes:
    """transforme une image en sticker statique 512px webp"""
    im = Image.open(BytesIO(data))
    if im.mode != 'RGBA':
        im = im.convert('RGBA')

    im = _apply_shape(im, shape)
    im = draw_watermark(im, watermark, shape, color)

    out = BytesIO()
    im.save(out, 'WEBP', quality=90, method=6)
    return out.getvalue()


# --------------------------------------------------------------------------
# videos
# --------------------------------------------------------------------------

def _video_filters(tmp: str, shape: str, watermark: str, fps: int, color: str = DEFAULT_COLOR, suffix: str = ".mp4") -> list:
    """construit les arguments -filter_complex pour ffmpeg"""
    steps = [f'scale={STICKER_SIZE}:{STICKER_SIZE}:force_original_aspect_ratio=decrease']

    if shape == SHAPE_SQUARE:
        # la transparence doit exister AVANT le pad pour avoir des bords transparents
        steps.append('format=yuva420p')
        steps.append(
            f'pad={STICKER_SIZE}:{STICKER_SIZE}:(ow-iw)/2:(oh-ih)/2:color=black@0'
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
        # IMPORTANT : le masque est borne a la duree max, sinon ffmpeg
        # tourne a l'infini et le sticker n'arrive jamais
        inputs = [
            '-loop', '1', '-framerate', str(fps),
            '-t', str(VIDEO_MAX_SECONDS), '-i', mask_path,
        ]
        chain += (
            f';[1:v]scale={STICKER_SIZE}:{STICKER_SIZE},format=gray[m]'
            f';[v][m]alphamerge[vm]'
        )
        last = '[vm]'

    if (watermark or '').strip():
        # Probe actual dimensions: original videos are not necessarily square.
        import json
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height',
             '-select_streams', 'v:0', '-of', 'json', os.path.join(tmp, 'in' + suffix)],
            capture_output=True, timeout=FFMPEG_TIMEOUT, check=True,
        )
        stream = json.loads(probe.stdout)['streams'][0]
        width = height = STICKER_SIZE
        if shape == SHAPE_ORIGINAL:
            ratio = STICKER_SIZE / max(stream['width'], stream['height'])
            width = max(2, int(stream['width'] * ratio) // 2 * 2)
            height = max(2, int(stream['height'] * ratio) // 2 * 2)
            # Explicit dimensions keep the overlay aligned with the video.
            chain = chain.replace(steps[0], f'scale={width}:{height}', 1)
        overlay_path = os.path.join(tmp, 'watermark.png')
        watermark_layer(width, height, watermark, shape, color).save(overlay_path)
        overlay_index = 2 if shape == SHAPE_ROUND else 1
        inputs += ['-loop', '1', '-framerate', str(fps), '-t', str(VIDEO_MAX_SECONDS), '-i', overlay_path]
        chain += f';{last}[{overlay_index}:v]overlay=0:0:shortest=1:format=auto,format=yuva420p[vw]'
        last = '[vw]'

    return inputs, chain, last


def video_to_webm(
    data: bytes,
    suffix: str = '.mp4',
    shape: str = SHAPE_ORIGINAL,
    watermark: str = '',
    color: str = DEFAULT_COLOR,
) -> bytes:
    """convertit une video / GIF en sticker video webm VP9 (512px, 3s max, 30fps)"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in' + suffix)
        dst = os.path.join(tmp, 'out.webm')
        with open(src, 'wb') as fh:
            fh.write(data)

        inputs, chain, last = _video_filters(tmp, shape, watermark, 30, color, suffix)

        out = b''
        for crf in (32, 40, 50):
            _run([
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-t', str(VIDEO_MAX_SECONDS), '-i', src, *inputs,
                '-filter_complex', chain, '-map', last,
                '-t', str(VIDEO_MAX_SECONDS),
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
    color: str = DEFAULT_COLOR,
) -> bytes:
    """convertit une video/webm en webp anime (format attendu par WhatsApp)"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in' + suffix)
        dst = os.path.join(tmp, 'out.webp')
        with open(src, 'wb') as fh:
            fh.write(data)

        inputs, chain, last = _video_filters(tmp, shape, watermark, 15, color, suffix)

        _run([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-t', str(VIDEO_MAX_SECONDS), '-i', src, *inputs,
            '-filter_complex', chain, '-map', last,
            '-t', str(VIDEO_MAX_SECONDS),
            '-loop', '0', '-an', '-fps_mode', 'passthrough',
            '-c:v', 'libwebp', '-quality', '55', '-compression_level', '6',
            dst,
        ])
        return open(dst, 'rb').read()


def to_wa_webp(data: bytes, suffix: str, shape: str = SHAPE_ORIGINAL, watermark: str = '', color: str = DEFAULT_COLOR) -> bytes:
    """point d'entree unique pour WhatsApp : renvoie toujours du webp"""
    if suffix in ('.webm', '.mp4', '.gif'):
        return any_to_animated_webp(data, suffix, shape, watermark, color)
    return image_to_webp(data, shape, watermark, color)
