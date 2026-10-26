import numpy as np
import pytest
from pydantic import ValidationError

from backend.style import Layout, MEDAL_COLORS
from backend.title_render import render_title


def colored_pixels(image, color):
    rgba = np.array(image)
    rgb = np.array([int(color[i:i+2],16) for i in (0,2,4)])
    return ((np.abs(rgba[:,:,:3].astype(int)-rgb).max(axis=2)<3)&(rgba[:,:,3]>245)).sum()


@pytest.mark.parametrize('style', ['plain', 'outline', 'shadow', 'box'])
def test_word_color_is_local_and_survives_each_title_theme(style):
    layout = Layout(title_style=style, title_highlights=[{'word':'fails','color':'FFD84D'}])
    image = render_title('Winter FAILS failsafe', layout, 720, 1280)
    assert colored_pixels(image, 'FFD84D')>100
    assert colored_pixels(image, 'FFFFFF')>100
    # Exact words, not substrings. The title renderer never interprets text as
    # markup or FFmpeg expressions; words which do not match stay neutral.
    unrelated = render_title(r'failsafe %{n} {style} \\path', layout, 720, 1280)
    assert colored_pixels(unrelated, 'FFD84D')==0
    plain = render_title('Winter FAILS failsafe', Layout(title_style='plain', title_highlights=layout.title_highlights), 720, 1280)
    if style!='plain':
        rgba = np.array(image)
        black = (rgba[:,:,:3].max(axis=2)<10)&(rgba[:,:,3]>20)
        assert black.sum()>100
        assert image.tobytes()!=plain.tobytes()


def test_invalid_highlight_cannot_inject_styles_or_filters():
    with pytest.raises(ValidationError):
        Layout(title_highlights=[{'word':'fails','color':'yellow;movie=/private'}])
    with pytest.raises(ValidationError):
        Layout(title_highlights=[{'word':'two words','color':'FFD84D'}])
    with pytest.raises(ValidationError):
        Layout(title_style='arbitrary-filter')


def test_wrapped_highlight_keeps_its_color_and_title_stays_bounded():
    text = 'Supercalifragilisticexpialidocious'
    layout = Layout(title_align='left',title_x=.7,title_size=.055,title_highlights=[{'word':text,'color':'FF5588'}])
    image = render_title(text,layout,720,1280)
    rgba = np.array(image)
    colored = (rgba[:,:,0]>230)&(rgba[:,:,1]<130)&(rgba[:,:,2]>90)&(rgba[:,:,3]>240)
    ys = np.flatnonzero(colored.any(axis=1))
    assert len(np.flatnonzero(np.diff(ys)>3))>=2
    assert image.height<1280


@pytest.mark.parametrize('active', range(1,6))
def test_medal_colors_are_stable_for_every_active_position(active):
    markers=Layout().rank_markers(active)
    assert [item['color'] for item in markers]==[MEDAL_COLORS[i] for i in range(1,6)]
    assert all(item['alpha']==1 for item in markers)
    assert [item['rank'] for item in markers if item['active']]==[active]
    assert Layout(rank_display='single').rank_markers(active)[0]['color']==MEDAL_COLORS[active]
