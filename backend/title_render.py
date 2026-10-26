"""Render safe, word-colored title artwork using the bundled font files."""
from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .style import FONTS, Layout


def render_title(text: str, layout: Layout, width: int, height: int, *, fonts=None):
    font_name = layout.font if layout.title_font == 'inherit' else layout.title_font
    size = max(1, round(width * layout.title_size))
    font = ImageFont.truetype((fonts or FONTS)[font_name], size)
    colors = {item.word.lower(): item.color for item in layout.title_highlights}
    margin = round(width*layout.title_x)
    left, right = ((margin, round(width*.95)) if layout.title_align == 'left' else
                   (round(width*.05), width-margin) if layout.title_align == 'right' else
                   (round(width*.05), round(width*.95)))
    available = max(1, right-left)
    lines, line, line_width = [], [], 0.0
    space = font.getlength(' ')
    for word in text.split():
        # Long words keep their color when wrapping across multiple lines.
        pieces, piece = [], ''
        for char in word:
            if piece and font.getlength(piece+char) > available:
                pieces.append(piece)
                piece = ''
            piece += char
        if piece:
            pieces.append(piece)
        for index, piece in enumerate(pieces):
            advance = font.getlength(piece)
            if line and line_width+space+advance > available:
                lines.append((line, line_width))
                line, line_width = [], 0.0
            if line:
                line.append((' ', layout.title_color))
                line_width += space
            line.append((piece, colors.get(word.lower(), layout.title_color)))
            line_width += advance
            if index < len(pieces)-1:
                lines.append((line, line_width))
                line, line_width = [], 0.0
    if line:
        lines.append((line, line_width))
    if not lines:
        return Image.new('RGBA', (width, 1))
    top = round(height*layout.title_y)
    line_height = max(1, round(size*1.17))
    ascent = font.getmetrics()[0]
    padding = max(1, round(width*.01))
    stroke = max(1, round(width*.003)) if layout.title_style == 'outline' else 0
    runs = []
    bottom = top
    for index, (line, line_width) in enumerate(lines):
        x = left if layout.title_align == 'left' else right-line_width if layout.title_align == 'right' else (width-line_width)/2
        baseline = top+index*line_height+ascent
        for part, color in line:
            runs.append((x, baseline, part, color))
            bottom = max(bottom, baseline+font.getbbox(part, anchor='ls')[3])
            x += font.getlength(part)
    needed = math.ceil(bottom+padding+stroke+width*.01)
    if needed > height:
        raise ValueError('Nadpis se při této velikosti nevejde do videa. Zmenšete písmo nebo posuňte nadpis výš.')
    image = Image.new('RGBA', (width, needed))
    draw = ImageDraw.Draw(image)
    if layout.title_style == 'box':
        draw.rounded_rectangle((max(0, left-padding), max(0, top-padding), min(width-1, right+padding), bottom+padding), radius=round(width*.008), fill=(0, 0, 0, 170))
    if layout.title_style == 'shadow':
        shadow = Image.new('RGBA', image.size)
        shadow_draw = ImageDraw.Draw(shadow)
        for x, y, part, _ in runs:
            shadow_draw.text((x+round(width*.003), y+round(width*.004)), part, font=font, fill=(0, 0, 0, 210), anchor='ls')
        image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(max(1, width*.002))))
        draw = ImageDraw.Draw(image)
    for x, y, part, color in runs:
        draw.text((x, y), part, font=font, fill='#'+color, anchor='ls', stroke_width=stroke, stroke_fill=(0, 0, 0, 230))
    return image
