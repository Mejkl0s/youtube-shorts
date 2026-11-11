import hashlib
import json
import uuid

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from backend import main as m,cleanup as c
from backend.overlay_geometry import join_rows, colored_symbols, persistent_symbols, complete_caption
from test_workflow import isolated


def caption_frame(path):
    image=Image.new('RGB',(720,1280),(15,25,75));draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(m.FONTS['bold'],42)
    draw.text((53,293),'FUNNY KID FAILS',font=font,fill='black',stroke_width=4,stroke_fill='black')
    draw.text((50,290),'FUNNY KID FAILS',font=font,fill='white',stroke_width=2,stroke_fill='black')
    for x in (530,598):
        draw.ellipse((x-28,290,x+28,346),fill=(255,205,0),outline='black',width=2)
        draw.ellipse((x-12,303,x-7,311),fill='black');draw.ellipse((x+7,303,x+12,311),fill='black')
        draw.arc((x-14,311,x+14,334),0,180,fill='black',width=3)
    image.save(path)
    return image


def covers(region,x,y):
    return region['x']*720<=x<=(region['x']+region['w'])*720 and region['y']*1280<=y<=(region['y']+region['h'])*1280


def test_ocr_keeps_weak_words_punctuation_and_both_page_modes(monkeypatch,tmp_path):
    headers='level\tblock_num\tpar_num\tline_num\tconf\ttext\tleft\ttop\twidth\theight\n'
    body='5\t1\t1\t1\t95\tFULL\t50\t100\t80\t35\n5\t1\t1\t1\t19\tTITLE\t140\t100\t95\t35\n5\t1\t1\t1\t20\t!!\t240\t100\t30\t35\n'
    calls=[]
    monkeypatch.setattr(m,'run',lambda args,*rest:(calls.append(args[args.index('--psm')+1]) or (headers+body).encode()))
    lines=c.text_lines(tmp_path/'frame.png')
    assert calls==['11','6'] and len(lines)==2
    assert all(len(words)==3 for words in lines.values())
    assert join_rows(lines.values())==[(50,100,270,135)]


@pytest.mark.parametrize('symbol_color',[(255,205,0),(255,255,255)])
def test_complete_row_includes_two_unreadable_emoji_but_not_distant_scene_object(tmp_path,symbol_color):
    image=caption_frame(tmp_path/'frame.png')
    draw=ImageDraw.Draw(image)
    for x in (530,598):draw.ellipse((x-28,290,x+28,346),fill=symbol_color,outline='black',width=2)
    draw.ellipse((640,800,700,860),fill='orange')
    groups=[colored_symbols(image,(0,0,1,1)) for _ in range(3)]
    stable=persistent_symbols(groups)
    box=complete_caption((50,298,452,333),stable,(0,0,1,1))
    assert box['right']*720>628 and box['bottom']*1280>346
    assert box['bottom']*1280<400
    assert complete_caption((1,10,100,40),[],(0,0,1,1))['x']==0
    # A moving bright ball in only one frame cannot extend the caption.
    assert persistent_symbols([[(500,300,550,350)],[],[]])==[]


def test_visual_review_accepts_standalone_temporary_emoji_and_rejects_low_confidence(monkeypatch):
    from backend import local_vision
    monkeypatch.delenv('RANK_DESKTOP_MODE',raising=False)
    monkeypatch.setattr(local_vision,'status',lambda:{'ready':True})
    def request(prompt,evidence,tokens):
        assert 'standalone' in prompt and 'COMPLETE text rows' in prompt
        assert len([b for b in evidence if b['type']=='image_url'])==1
        return {'regions':[{'x':.6,'y':.4,'w':.1,'h':.06,'kind':'emoji','method':'remove','confidence':.98,'seen_frames':1},
                           {'x':.1,'y':.5,'w':.1,'h':.1,'kind':'emoji','method':'blur','confidence':.4,'seen_frames':1}]}
    monkeypatch.setattr(local_vision,'request',request)
    result,used=c.vision_regions([Image.new('RGB',(720,1280))],(0,0,1,1))
    assert used and len(result)==1 and result[0]['kind']=='emoji' and result[0]['method']=='blur'


def test_real_ocr_detects_complete_title_and_emoji_and_real_export_hides_them(isolated,monkeypatch):
    frame=isolated/'caption.png';original=caption_frame(frame)
    source=isolated/'caption.mp4'
    m.ffmpeg('-loop','1','-i',str(frame),'-t','1.2','-r','15','-c:v','libx264','-pix_fmt','yuv420p',str(source))
    monkeypatch.setattr(c,'vision_regions',lambda *args:([],False))
    regions,message=c.detect_text(source,0,1.2,'fit')
    for point in ((52,302),(450,326),(505,292),(555,344),(574,292),(624,344)):
        assert any(covers(r,*point) for r in regions),(point,regions,message)
    assert sum(r['w']*r['h'] for r in regions)<=.35
    clips=[]
    for _ in range(5):
        identity=uuid.uuid4().hex;folder=isolated/'media'/identity;folder.mkdir()
        import shutil
        shutil.copyfile(source,folder/'source')
        meta=m.register(folder/'source',identity,'Caption',fast_preview=True)
        clips.append({**meta,'title':'Caption','voiceover':'','duration':1,'blur_regions':regions})
    project=m.Project(title='MY OWN TITLE',clips=clips,voice=False,effects=False,captions=False,resolution='720',layout=m.Layout(header_darkness=0))
    identity=uuid.uuid4().hex;m.jobs[identity]={'id':identity};m.render(identity,project)
    assert m.jobs[identity]['status']=='done',m.jobs[identity]
    raw=m.ffmpeg('-ss','0.6','-i',str(isolated/'jobs'/identity/'ranking.mp4'),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1')
    output=np.frombuffer(raw,np.uint8).reshape(1280,720,3)
    # No sharp title letters or emoji eyes remain within the source caption.
    before=np.asarray(original)[290:347,45:632].astype(float)
    after=output[290:347,45:632].astype(float)
    contrast=lambda image:np.abs(np.diff(image,axis=1)).mean()
    assert contrast(after)<contrast(before)*.25
    # Uncovered source pixels and the editor's own title remain intact/sharp.
    assert np.abs(output[800:900,650:700].astype(float)-[15,25,75]).mean()<6
    assert (np.max(np.abs(np.diff(output[20:180].astype(float),axis=1)),axis=2)>90).sum()>100


def test_packaging_stages_ocr_runtime_language_and_manifest_without_system_dependency(tmp_path,monkeypatch):
    from scripts import build_desktop as b
    source=tmp_path/'verified';source.mkdir();(source/'tessdata').mkdir()
    for name,data in {'tesseract.exe':b'EXE fixture','liblept.dll':b'DLL fixture','LICENSE.txt':b'License fixture','tessdata/eng.traineddata':b'Language fixture'}.items():
        (source/name).write_bytes(data)
    monkeypatch.setenv('RANK_OCR_SOURCE',str(source));monkeypatch.setattr(b,'TOOLS',tmp_path/'tools');b.TOOLS.mkdir()
    monkeypatch.setattr(b.subprocess,'check_output',lambda args,**kw:'eng\n' if '--list-langs' in args else 'tesseract v5.4.0.20240606')
    target=b.stage_ocr()
    sums=json.loads((target/'SHA256SUMS.json').read_text())
    for name in ('tesseract.exe','liblept.dll','LICENSE.txt','tessdata/eng.traineddata'):
        assert sums[name]==hashlib.sha256((source/name).read_bytes()).hexdigest()
    monkeypatch.delenv('RANK_OCR_SOURCE')
    with pytest.raises(RuntimeError,match='RANK_OCR_SOURCE'):b.stage_ocr()
