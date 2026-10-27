"""Bounded source-text detection and blur, before the editor's own overlays."""
import csv
import io
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class BlurRegion(BaseModel):
    x: float = Field(ge=0, le=.99, allow_inf_nan=False)
    y: float = Field(ge=0, le=.99, allow_inf_nan=False)
    w: float = Field(ge=.01, le=1, allow_inf_nan=False)
    h: float = Field(ge=.01, le=1, allow_inf_nan=False)
    origin: str = Field(default='manual', pattern='^(auto|manual)$')

    @model_validator(mode='after')
    def in_frame(self):
        if self.x + self.w > 1.000001 or self.y + self.h > 1.000001:
            raise ValueError('Oblast rozmazání musí zůstat uvnitř obrazu.')
        return self


def blur_filters(regions, width, height, source='source_clean'):
    """The source has already been transformed to the final portrait frame."""
    filters = []
    for index, region in enumerate(regions):
        x, y = int(region.x * width) // 2 * 2, int(region.y * height) // 2 * 2
        w = min(width-x, max(2, round(region.w*width/2)*2))
        h = min(height-y, max(2, round(region.h*height/2)*2))
        base, patch, blurred, output = (f'blur_{label}_{index}' for label in ('base', 'patch', 'patch_done', 'out'))
        filters.extend([f'[{source}]split=2[{base}][{patch}]',
                        f'[{patch}]crop={w}:{h}:{x}:{y},gblur=sigma={max(5, width*.025):.2f}:steps=2[{blurred}]',
                        f'[{base}][{blurred}]overlay={x}:{y}:shortest=1[{output}]'])
        source = output
    return filters, source


def text_lines(frame):
    from . import main as m
    for mode, confidence in (('11', 60), ('6', 75)):
        tsv = m.run(['tesseract', str(frame), 'stdout', '-l', 'eng', '--psm', mode, 'tsv'], 20).decode(errors='replace')
        lines = {}
        for row in csv.DictReader(io.StringIO(tsv), delimiter='\t'):
            try:
                if int(row['level']) != 5 or float(row['conf']) < confidence or not any(c.isalnum() for c in row['text']):
                    continue
                key = tuple(row[name] for name in ('block_num', 'par_num', 'line_num'))
                lines.setdefault(key, []).append(tuple(int(row[name]) for name in ('left', 'top', 'width', 'height')))
            except (KeyError, ValueError):
                continue
        if lines:
            return lines
        # Sparse OCR sometimes skips a bright caption inside a dark rectangle.
        # Try the block mode once, with a higher confidence requirement.
    return {}


def detect_text(path: Path, start: float, duration: float, framing='fill'):
    """Find text lines on three real portrait frames. Masks cover the whole clip.

    OCR is an editable suggestion, not a guarantee of identifying every overlay.
    Returned text itself is deliberately discarded.
    """
    from . import main as m
    from .scene_context import portrait_filter
    if not shutil.which('tesseract'):
        return [], 'Rozpoznání textu není dostupné. Označ rušivé oblasti ručně.'
    boxes = []
    with tempfile.TemporaryDirectory(dir=m.DATA) as temporary:
        frame = Path(temporary)/'frame.png'
        for offset in (.15, .5, .85):
            m.ffmpeg('-ss', str(start+duration*offset), '-i', str(path), '-frames:v', '1',
                     '-vf', portrait_filter(720,1280,framing)+',format=gray', str(frame))
            for words in text_lines(frame).values():
                x = max(0, min(r[0] for r in words)-10)
                y = max(0, min(r[1] for r in words)-8)
                right = min(720, max(r[0]+r[2] for r in words)+10)
                bottom = min(1280, max(r[1]+r[3] for r in words)+8)
                if right-x < 15 or bottom-y < 13 or (right-x)*(bottom-y) > 720*1280*.2:
                    continue
                boxes.append([x/720, y/1280, right/720, bottom/1280])
    # Merge overlapping detections across frames, including slightly moving text.
    merged = []
    for box in boxes:
        pending = box
        while True:
            match = next((i for i, other in enumerate(merged)
                          if min(pending[2], other[2]) > max(pending[0], other[0])
                          and min(pending[3], other[3]) > max(pending[1], other[1])), None)
            if match is None:
                break
            other = merged.pop(match)
            pending = [min(pending[0],other[0]),min(pending[1],other[1]),max(pending[2],other[2]),max(pending[3],other[3])]
        merged.append(pending)
    # Never automatically blur most of the image, even with noisy OCR.
    regions, area = [], 0
    for x,y,right,bottom in sorted(merged, key=lambda b:(b[3]-b[1])*(b[2]-b[0]), reverse=True):
        size = (right-x)*(bottom-y)
        if size > .2 or area+size > .35 or len(regions) == 8:
            continue
        regions.append(BlurRegion(x=x,y=y,w=right-x,h=bottom-y,origin='auto').model_dump())
        area += size
    return regions, ('Nalezené oblasti zkontroluj; masky platí po celou délku klipu. Další nápisy nebo překážky označ ručně.' if regions
                     else 'V ukázkových snímcích nebyl rozpoznán text. Rušivé oblasti můžeš označit ručně.')
