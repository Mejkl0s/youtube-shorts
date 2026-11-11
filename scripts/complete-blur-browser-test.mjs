// Real OCR, manual expansion, persistence and actual MP4 cleanup. No model calls.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {execFileSync,spawn} from 'node:child_process';
import {mkdir,copyFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
const root=resolve('.runtime/complete-blur-browser-'+randomUUID());await mkdir(root,{recursive:true});
execFileSync('.venv/bin/python',['-c',`from PIL import Image,ImageDraw,ImageFont
import sys
im=Image.new('RGB',(720,1280),(15,25,75));d=ImageDraw.Draw(im);f=ImageFont.truetype(sys.argv[2],42)
d.text((50,290),'FUNNY KID FAILS',font=f,fill='white',stroke_width=2,stroke_fill='black')
for x in (530,598):
 d.ellipse((x-28,290,x+28,346),fill=(255,205,0),outline='black',width=2)
 d.ellipse((x-12,303,x-7,311),fill='black');d.ellipse((x+7,303,x+12,311),fill='black')
 d.arc((x-14,311,x+14,334),0,180,fill='black',width=3)
im.save(sys.argv[1])`,root+'/caption.png',resolve('backend/fonts/DejaVuSans-Bold.ttf')]);
execFileSync('ffmpeg',['-v','error','-y','-loop','1','-i',root+'/caption.png','-t','1.2','-r','15','-c:v','libx264','-pix_fmt','yuv420p',root+'/caption.mp4']);
const files=[];for(let i=0;i<5;i++){const path=root+`/caption-${i}.mp4`;await copyFile(root+'/caption.mp4',path);files.push(path);}
const reservation=createServer();await new Promise(done=>reservation.listen(0,'127.0.0.1',done));const port=reservation.address().port;await new Promise(done=>reservation.close(done));
const code=`from backend import main as m
m.local_vision.status=lambda **kw:{'ready':False,'supported':True,'model':'not-used','message':'OCR-only fixture'}
import uvicorn,sys
uvicorn.run(m.app,host='127.0.0.1',port=int(sys.argv[1]),log_level='error')`;
const env={...process.env,RANK_DATA_DIR:root+'/data',STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1'};delete env.RANK_DESKTOP_MODE;delete env.OPENAI_API_KEY;delete env.ELEVENLABS_API_KEY;
const server=spawn('.venv/bin/python',['-c',code,String(port)],{env,stdio:['ignore','pipe','pipe']});let browser,logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
try{
 const base=`http://127.0.0.1:${port}`;
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await new Promise(done=>setTimeout(done,100));}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('input[type=file][multiple]').setInputFiles(files);
 await page.waitForFunction(()=>document.querySelectorAll('.clip-thumb img').length===5,{},{timeout:60000});
 await page.locator('.clip-card').first().getByRole('button',{name:/^Rozmazání/}).click();
 const dialog=page.getByRole('dialog',{name:'Rozmazání klipu 5',exact:true});await dialog.waitFor();
 await dialog.getByRole('button',{name:'Najít celé nápisy, emoji, loga a bloky',exact:true}).click();
 await dialog.locator('.cleanup-region').first().waitFor({timeout:60000});
 const box=await dialog.locator('.cleanup-region').first().boundingBox();
 await dialog.getByRole('button',{name:'Zvětšit oblast 1',exact:true}).click();
 const expanded=await dialog.locator('.cleanup-region').first().boundingBox();assert.ok(expanded.width>box.width&&expanded.height>box.height);
 await dialog.getByRole('button',{name:'Použít úpravy obrazu',exact:true}).click();
 await page.locator('.save-button').click();await page.reload();
 await page.waitForFunction(()=>document.querySelectorAll('.clip-thumb img').length===5);
 const state=await page.evaluate(()=>JSON.parse(localStorage.getItem('rank-studio-project')));
 const regions=state.clips[0].blur_regions;
 assert.ok(regions.some(r=>r.x*720<52&&(r.x+r.w)*720>626&&r.y*1280<299&&(r.y+r.h)*1280>344));
 assert.ok(await page.locator('.phone .source-cleanup-masks span').first().evaluate(el=>getComputedStyle(el).backdropFilter.includes('blur(')));
 for(const [role,name] of [['switch','AI voiceover'],['switch','Zvukové efekty'],['switch','Poznámky u čísel']]){const toggle=page.getByRole(role,{name,exact:true});if(await toggle.getAttribute('aria-checked')==='true')await toggle.click();}
 await page.locator('#resolution').selectOption('720');await page.getByRole('button',{name:'Vytvořit náhled se zvukem',exact:true}).click();
 const finished=page.getByRole('region',{name:'Hotové video',exact:true});await finished.waitFor({timeout:90000});
 const url=await page.getByLabel('Přehrávač hotového Shortu',{exact:true}).getAttribute('src');const response=await fetch(base+url);assert.equal(response.status,200);
 assert.ok((await response.arrayBuffer()).byteLength>1000);
 assert.deepEqual(errors,[]);
 await mkdir('.runtime/screenshots',{recursive:true});
 await page.locator('.clip-card').first().getByRole('button',{name:/^Rozmazání/}).click();
 await page.getByRole('dialog',{name:'Rozmazání klipu 5',exact:true}).screenshot({path:'.runtime/screenshots/complete-title-and-emoji-blur.png'});
 console.log('Complete blur passed: actual title/emoji OCR, editable wider masks, preview blur, saved regions and real MP4 export; no AI provider used.');
}catch(error){console.error(logs);throw error;}finally{if(browser)await browser.close();server.kill('SIGTERM');}
