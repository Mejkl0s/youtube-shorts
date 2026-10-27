"""Short editable reactions beside the ranking numbers, independent of speech."""
from PIL import ImageFont

DEFAULT_NOTES = ['Wait for it', 'So close!', 'Oops!', 'No way!', 'What a finale!']  # #5 → #1


def note_geometry(text, font_path, marker, width, height, rank_x):
    number_font = ImageFont.truetype(font_path, int(width*marker['size']))
    x = int(width*rank_x + number_font.getlength(marker['text']) + width*.018)
    available = max(1, width-x-int(width*.035))
    size = int(width*.032)
    font = ImageFont.truetype(font_path, size)
    while size > 6 and font.getlength(text) > available:
        size -= 1
        font = ImageFont.truetype(font_path, size)
    number_box = number_font.getbbox(marker['text'])
    note_box = font.getbbox(text)
    y = int(height*marker['y'] + max(0, (number_box[3]-number_box[1] - note_box[3]+note_box[1])/2))
    return x, y, size
