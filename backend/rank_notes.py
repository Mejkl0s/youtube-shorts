"""Short editable reactions beside the ranking numbers, independent of speech."""
from PIL import ImageFont
import random
import threading
from collections import deque

NOTE_BANK = {
    'en': ['Wait for it', 'So close!', 'Oops!', 'No way!', 'What a finale!', 'Plot twist!',
           'Well, then...', 'That happened!', 'Here we go', 'One more try?', 'Oh dear!',
           'Hold on...', 'What just happened?', 'The suspense!', 'Take two?', 'A little surprise',
           'Oh no!', 'Quite a moment', 'Unexpected!', 'Cue the replay', 'Not quite...',
           'Worth a replay', 'Big moment!', 'Well, that escalated', 'There it is!'],
    'cs': ['Počkej si', 'Tak blízko!', 'Ups!', 'To snad ne!', 'Velké finále!', 'Zvrat!',
           'No tedy...', 'Tak tohle!', 'A je to', 'Ještě jeden pokus?', 'To je moment',
           'Vydrž...', 'Co se stalo?', 'To je napětí!', 'Druhý pokus?', 'Malé překvapení',
           'Ale ne!', 'Nečekané!', 'Znovu, prosím', 'To úplně nevyšlo', 'Stojí za opakování',
           'Velký moment!', 'Tak to překvapilo', 'A máme to!', 'No páni!'],
}
_recent = {key: deque(maxlen=10) for key in NOTE_BANK}
_last_set = {key: [] for key in NOTE_BANK}
_lock = threading.Lock()


def fresh_notes(count=5, language='en', exclude=()):
    language = language if language in NOTE_BANK else 'en'
    with _lock:
        bank = NOTE_BANK[language]
        exclude=set(exclude)|set(_last_set[language] if count>1 else ())
        available = [text for text in bank if text not in exclude and text not in _recent[language]]
        if len(available)<count:
            available=[text for text in bank if text not in exclude]
        if len(available)<count:
            available=bank
        result=random.SystemRandom().sample(available,count)
        _recent[language].extend(result)
        if count>1:
            _last_set[language]=result
        return result


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
