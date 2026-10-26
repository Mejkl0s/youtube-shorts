import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import ImageFont
from pydantic import ValidationError

from backend import main as m
from backend.style import FONT_CATALOG, FONT_DIR, FONTS, Layout
from backend.title_render import render_title


def test_shared_catalog_matches_font_validation_and_bundled_sources():
    names={entry['id'] for entry in FONT_CATALOG}
    assert len(names)==12 and names==set(FONTS)
    schema=Layout.model_json_schema()['properties']
    assert set(schema['font']['enum'])==names
    assert set(schema['title_font']['enum'])==names|{'inherit'}
    for row in json.loads((FONT_DIR/'sources.json').read_text()):
        data=(FONT_DIR/row['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==row['sha256']
        assert (FONT_DIR/row['license']).is_file()
        assert ImageFont.truetype(str(FONT_DIR/row['file']),32).getname()[0]==row['family']
        face=ImageFont.truetype(str(FONT_DIR/row['file']),32)
        try:
            assert not face.get_variation_axes(), 'Bundle static faces to keep browser and export weights identical.'
        except OSError:
            pass

    with pytest.raises(ValidationError):
        Layout(title_font='../../private.ttf')


@pytest.mark.parametrize('entry',FONT_CATALOG,ids=lambda entry:entry['id'])
def test_named_font_is_served_and_renders_the_same_bundled_face(entry,monkeypatch):
    for key in ('STUDIO_PASSWORD','STUDIO_PUBLIC'):
        monkeypatch.delenv(key,raising=False)
    path=Path(FONTS[entry['id']])
    assert (FONT_DIR/entry['license']).is_file()
    response=TestClient(m.app).get('/api/fonts/'+entry['id'])
    assert response.status_code==200
    assert response.headers['content-type'].startswith('font/ttf')
    assert response.content==path.read_bytes()
    image=render_title('Ranking Žlutý kůň 123',Layout(title_font=entry['id']),720,1280)
    assert (np.array(image)[:,:,3]>200).sum()>500
