"""Conversion des medias vers les formats acceptes par Telegram / WhatsApp."""

import logging
import os
import subprocess
import tempfile
from io import BytesIO

from PIL import Image

logger = logging.getLogger(__name__)

STICKER_SIZE = 512
VIDEO_MAX_SECONDS = 3
VIDEO_MAX_BYTES = 256 * 1024


def _run(args):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode('utf-8', 'ignore')[-400:])


def image_to_webp(data: bytes) -> bytes:
    """redimensionne une image pour en faire un sticker statique 512px webp"""
    im = Image.open(BytesIO(data))
    if im.mode != 'RGBA':
        im = im.convert('RGBA')

    ratio = STICKER_SIZE / max(im.width, im.height)
    new_size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
    im = im.resize(new_size, Image.LANCZOS)

    # un cote au moins doit faire exactement 512px
    if im.width != STICKER_SIZE and im.height != STICKER_SIZE:
        im = im.resize((STICKER_SIZE, STICKER_SIZE), Image.LANCZOS)

    out = BytesIO()
    im.save(out, 'WEBP', quality=90, method=6)
    return out.getvalue()


def video_to_webm(data: bytes, suffix: str = '.mp4') -> bytes:
    """convertit une video / GIF en sticker video webm VP9 (512px, 3s max, 30fps)"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in' + suffix)
        dst = os.path.join(tmp, 'out.webm')
        with open(src, 'wb') as fh:
            fh.write(data)

        vf = (
            f'scale={STICKER_SIZE}:{STICKER_SIZE}:force_original_aspect_ratio=decrease,'
            f'fps=30'
        )

        for crf in (32, 40, 50):
            _run([
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-t', str(VIDEO_MAX_SECONDS), '-i', src,
                '-vf', vf,
                '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', str(crf),
                '-an', '-pix_fmt', 'yuva420p',
                '-f', 'webm', dst,
            ])
            out = open(dst, 'rb').read()
            if len(out) <= VIDEO_MAX_BYTES:
                return out
        return out


def any_to_animated_webp(data: bytes, suffix: str) -> bytes:
    """convertit une video/webm en webp anime (format attendu par WhatsApp)"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in' + suffix)
        dst = os.path.join(tmp, 'out.webp')
        with open(src, 'wb') as fh:
            fh.write(data)
        _run([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-t', str(VIDEO_MAX_SECONDS), '-i', src,
            '-vf', f'scale={STICKER_SIZE}:{STICKER_SIZE}:force_original_aspect_ratio=decrease,fps=15',
            '-loop', '0', '-an', '-vsync', '0',
            '-c:v', 'libwebp', '-quality', '55', '-compression_level', '6',
            dst,
        ])
        return open(dst, 'rb').read()


def to_wa_webp(data: bytes, suffix: str) -> bytes:
    """point d'entree unique pour WhatsApp : renvoie toujours du webp"""
    if suffix in ('.webm', '.mp4', '.gif'):
        return any_to_animated_webp(data, suffix)
    return image_to_webp(data)
