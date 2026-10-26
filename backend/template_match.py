"""Approximate a ranking layout locally from real OCR boxes and image pixels."""
import csv
import io
import re
import shutil

import numpy as np

from .style import Layout


def color_for_box(image, box):
    x, y, width, height = [int(box[key]) for key in ('left', 'top', 'width', 'height')]
    crop = image[max(0, y):y + height, max(0, x):x + width]
    if not crop.size:
        return 'FFFFFF'
    pixels = crop.reshape(-1, 3).astype(np.int16)
    border = np.concatenate((crop[0], crop[-1], crop[:, 0], crop[:, -1])).astype(np.int16)
    background = np.median(border, axis=0)
    foreground = pixels[np.max(np.abs(pixels - background), axis=1) > 65]
    if not len(foreground):
        foreground = pixels
    bright = foreground[foreground.max(axis=1) > 150]
    if len(bright) >= max(4, len(foreground) * .08):
        foreground = bright
    bins = foreground // 32
    values, counts = np.unique(bins, axis=0, return_counts=True)
    dominant = values[counts.argmax()]
    color = np.median(foreground[np.all(bins == dominant, axis=1)], axis=0).astype(int)
    return ''.join(f'{int(channel):02X}' for channel in color)


def local_match(path, base: Layout):
    from . import main as m
    layout = base.model_copy()
    if not shutil.which('tesseract'):
        return layout, [], 'Lokální rozpoznání textu není na serveru dostupné. Vzhled nastav ručně níže.'
    metadata = m.probe(path)['streams'][0]
    width, height = metadata['width'], metadata['height']
    raw = m.ffmpeg('-i', str(path), '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1')
    image = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
    tsv = m.run(['tesseract', str(path), 'stdout', '-l', 'eng', '--psm', '11', 'tsv'], 30).decode(errors='replace')
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t'):
        try:
            if int(row['level']) == 5 and float(row['conf']) >= 35 and row['text'].strip():
                words.append({**row, **{key: int(row[key]) for key in ('left', 'top', 'width', 'height')}})
        except (KeyError, ValueError):
            continue
    detected = []
    numbers = [word for word in words if re.fullmatch(r'[#(\s]*[1-5][.)\s]*', word['text'])
               and .04 <= word['top'] / height <= .65 and word['height'] / height >= .02]
    rank = max(numbers, key=lambda word: word['height'] * (2 if '#' in word['text'] else 1), default=None)
    if rank is None:
        # Large isolated markers such as #5 can be read as letters; only infer their box.
        markers = [word for word in words if len(word['text']) <= 4 and word['height'] / width >= .065
                   and .12 <= word['top'] / height <= .65 and word['width'] / width < .45]
        rank = max(markers, key=lambda word: word['height'], default=None)
    if rank:
        layout.rank_x = min(.8, max(.01, rank['left'] / width))
        layout.rank_y = min(.65, max(.05, rank['top'] / height))
        layout.rank_size = min(.24, max(.05, rank['height'] / width / .75))
        layout.rank_color = color_for_box(image, rank)
        layout.rank_palette = 'custom'
        detected.append('číslo')
    lines = {}
    for word in words:
        if word is rank or re.fullmatch(r'[#\d\W]+', word['text']):
            continue
        key = tuple(word.get(part) for part in ('block_num', 'par_num', 'line_num'))
        lines.setdefault(key, []).append(word)
    groups = []
    for items in lines.values():
        left = min(item['left'] for item in items)
        top = min(item['top'] for item in items)
        right = max(item['left'] + item['width'] for item in items)
        bottom = max(item['top'] + item['height'] for item in items)
        groups.append({'left': left, 'top': top, 'width': right-left, 'height': bottom-top, 'words': items})
    title = max((line for line in groups if .01 <= line['top'] / height <= .35),
                key=lambda line: line['height'] * (1 + min(len(line['words']), 3) / 3), default=None)
    caption = max((line for line in groups if .45 <= line['top'] / height <= .9),
                  key=lambda line: line['height'] * (1 + min(len(line['words']), 3) / 3), default=None)
    for name, box in (('title', title), ('caption', caption)):
        if box:
            limits = (.01, .35, .02, .085) if name == 'title' else (.45, .9, .025, .09)
            setattr(layout, name+'_y', min(limits[1], max(limits[0], box['top'] / height)))
            setattr(layout, name+'_size', min(limits[3], max(limits[2], box['height'] / width / .75)))
            setattr(layout, name+'_color', color_for_box(image, box))
            center = (box['left'] + box['width'] / 2) / width
            alignment = 'center' if abs(center - .5) < .1 else 'left' if center < .5 else 'right'
            margin = (box['left'] if alignment == 'left' else width - box['left'] - box['width']) / width
            setattr(layout, name+'_align', alignment)
            if alignment != 'center':
                setattr(layout, name+'_x', min(.75, max(.01, margin)))
            detected.append('nadpis' if name == 'title' else 'titulky')
    if detected:
        layout.show_label = False
        layout.show_criteria = False
    layout = Layout.model_validate(layout.model_dump())
    notes = ('Lokální odhad: ' + ', '.join(detected) + '. Zkontroluj polohy, barvy a velikosti v náhledu; písmo je nejbližší dostupné, animace ani hlas se nerozpoznávají.') if detected else 'V tomto snímku se nepodařilo rozpoznat nadpis, číslo ani titulky. Vyber jiný snímek videa nebo nastav vzhled ručně; dosavadní nastavení zůstalo zachované.'
    return layout, detected, notes
