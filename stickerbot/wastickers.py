"""Construction des fichiers .wastickers pour l'import vers WhatsApp."""

import math
import zipfile
from io import BytesIO
from typing import List, Tuple

from PIL import Image

TRAY_ICON_SIZE = 96
TRAY_ICON_MAX_BYTES = 50 * 1024
TITLE_MAX_LEN = 128
AUTHOR_MAX_LEN = 128
STICKERS_PER_FILE = 30


def build_tray_icon_png(first_sticker_webp: bytes) -> bytes:
    im = Image.open(BytesIO(first_sticker_webp)).convert('RGBA')
    size = TRAY_ICON_SIZE
    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))

    scale = min(size / im.width, size / im.height)
    new_w, new_h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)
    canvas.paste(im, ((size - new_w) // 2, (size - new_h) // 2), im)

    buf = BytesIO()
    canvas.save(buf, 'PNG', optimize=True)
    data = buf.getvalue()
    if len(data) > TRAY_ICON_MAX_BYTES:
        buf = BytesIO()
        canvas.convert('P', palette=Image.ADAPTIVE, colors=128).save(buf, 'PNG', optimize=True)
        data = buf.getvalue()
    return data


def _slugify(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum():
            keep.append(ch)
        elif ch in (' ', '_', '-'):
            keep.append('_')
    slug = ''.join(keep).strip('_')
    return slug[:60] if slug else 'pack'


def files_count_for(total: int, batch_size: int = STICKERS_PER_FILE) -> int:
    return max(1, math.ceil(total / batch_size))


def build_wastickers_files(
    title: str,
    author: str,
    stickers_webp: List[bytes],
    tray_icon_png: bytes,
    batch_size: int = STICKERS_PER_FILE,
) -> List[Tuple[str, BytesIO]]:
    if not stickers_webp:
        raise ValueError('aucun sticker a empaqueter')

    batches = [stickers_webp[i:i + batch_size] for i in range(0, len(stickers_webp), batch_size)]
    total_files = len(batches)

    safe_title = (title or 'Pack').strip()[:TITLE_MAX_LEN] or 'Pack'
    safe_author = (author or 'Stickers Bot').strip()[:AUTHOR_MAX_LEN] or 'Stickers Bot'

    results = []
    for part_index, batch in enumerate(batches, start=1):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            part_title = safe_title if total_files == 1 else f'{safe_title} ({part_index}/{total_files})'
            zf.writestr('title.txt', part_title[:TITLE_MAX_LEN])
            zf.writestr('author.txt', safe_author)
            zf.writestr('icon.png', tray_icon_png)
            for i, webp_bytes in enumerate(batch, start=1):
                zf.writestr(f'{i:02d}.webp', webp_bytes)
        buf.seek(0)

        base_name = _slugify(safe_title)
        filename = f'{base_name}.wastickers' if total_files == 1 else f'{base_name}_{part_index}.wastickers'
        results.append((filename, buf))

    return results
