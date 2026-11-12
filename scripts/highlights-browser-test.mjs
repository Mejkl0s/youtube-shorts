// Real retrieval orchestration, decoded frames/cuts and browser persistence.
// Network retrieval and AI JSON are fixtures; this is not a model-quality benchmark.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {execFileSync,spawn} from 'node:child_process';
import {mkdir,readFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
const root=resolve('.runtime/highlights-browser-'+randomUUID());await mkdir(root,{recursive:true});
for(let i=0;i<8;i++)execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=gray:s=320x180:r=15:d=8','-f','lavfi','-i','sine=frequency=440:duration=8','-vf',`drawbox=x=${i*30}:y=40:w=30:h=60:color=lime:t=fill:enable='gte(t,6.5)'`,'-c:v','libx264','-c:a','aac',`${root}/fixture-${i}.mp4`]);
const reservation=createServer();await new Promise(done=>reservation.listen(0,'127.0.0.1',done));const port=reservation.address().port;await new Promise(done=>reservation.close(done));
const code=`
import sys,shutil,uuid,json
from pathlib import Path
from backend import main as m
root=Path(sys.argv[1]);reviews=[]
rows=[{'url':('https://www.tiktok.com/@fixture/video/'+str(7000000000000000000+i) if i%3==0 else 'https://www.instagram.com/reel/HIGH'+str(i) if i%3==1 else 'https://www.youtube.com/shorts/HIGHL'+f'{i:06d}'),'title':f'Winter fails {i}'} for i in range(8)]
def download(item):
 i=next(i for i,row in enumerate(rows) if row['url']==item['url']);identity=uuid.uuid4().hex;folder=m.DATA/'media'/identity;folder.mkdir()
 shutil.copyfile(root/f'fixture-{i}.mp4',folder/'source')
 return {**m.register(folder/'source',identity,item['title'],fast_preview=True),'source':m.source_name(item['url']),'source_url':item['url']}
def request(prompt,evidence,tokens):
 assert any(row['type']=='image_url' for row in evidence)
 if 'PER-VIDEO SCOUT' in prompt:return {'shortlist':[{'start':5.5,'end':7.5,'action':6.5}]}
 if 'PER-VIDEO FINAL REVIEW' in prompt:
  reviews.append(evidence[0]['text']);(root/'reviews.json').write_text(json.dumps(reviews))
  return {'moments':[{'scene':0,'topic_match':True,'complete':True,'confidence':.95,'score':70+len(reviews),'start':5.5,'end':7.5,'setup':{'time':5.7,'observation':'Preparation visible'},'action':{'time':6.5,'observation':'Green action appears'},'outcome':{'time':7.1,'observation':'Green result remains'},'title':'Visible late event','voiceover':'The late result.','rank_note':'Late result','reason':'Complete visible event.'}]}
 if 'RANK NOTE REVIEW' in prompt:return {'visible':True,'note':'Green block appears'}
 if 'CUT AUDIT' in prompt:return {'accepted':True,'topic_match':True,'complete':True,'action_visible':True,'outcome_visible':True,'confidence':.95,'reason':'Result remains visible in the actual cut.'}
 if 'SET AUDIT' in prompt:return {'distinct':True,'duplicates':[],'confidence':.95,'reason':'Different positions of green event.'}
 raise AssertionError(prompt)
def forbidden(*args,**kwargs):raise AssertionError('Paid provider fallback is forbidden')
m.public_search=lambda *args,**kw:([r for r in rows if m.source_name(r['url'])!='YouTube'],[])
m.youtube_search=lambda *args,**kw:([r for r in rows if m.source_name(r['url'])=='YouTube'],[])
m.download_candidate=download;m.ai_request=forbidden;m.local_vision.request=request
m.local_vision.status=lambda **kw:{'supported':True,'ready':True,'model':m.local_vision.selected_model(),'message':'Local protocol fixture ready'}
import uvicorn
uvicorn.run(m.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
`;
const env={...process.env,RANK_DATA_DIR:root+'/data',STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1'};delete env.OPENAI_API_KEY;delete env.ELEVENLABS_API_KEY;
const server=spawn('.venv/bin/python',['-c',code,root,String(port)],{env,stdio:['ignore','pipe','pipe']});let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);let browser;
try{
 const base=`http://127.0.0.1:${port}`;
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await new Promise(done=>setTimeout(done,100));}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base);await page.locator('#topic').fill('winter fails');
 assert.equal(await page.getByLabel('Maximální délka projektu',{exact:true}).inputValue(),'40');
 await page.getByLabel('Rozsah hledání',{exact:true}).selectOption('thorough');
 assert.equal(await page.getByLabel('Počet kandidátů',{exact:true}).inputValue(),'100');
 assert.equal(await page.locator('#search-mode').inputValue(),'local');
 await page.getByLabel('Po hledání vytvořit hotový náhled').uncheck();await page.getByLabel('Voiceover',{exact:true}).uncheck();await page.getByLabel('Automaticky rozmazat nápisy, emoji a malá loga').uncheck();
 await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.visual-evidence').length===5,{},{timeout:120000});
 assert.equal(await page.getByLabel('Maximální délka projektu',{exact:true}).inputValue(),'25');
 assert.equal(JSON.parse(await readFile(root+'/reviews.json','utf8')).length,8);
 const diagnostics=page.getByRole('region',{name:'Výsledky jednotlivých zdrojů'});
 assert.equal(await diagnostics.locator('article').count(),3);assert.ok((await diagnostics.innerText()).includes('2 posouzeno'));
 await page.getByLabel('Barevný režim čísel',{exact:true}).selectOption('individual');
 await page.getByLabel('Barva čísla 1',{exact:true}).evaluate(el=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'#11cc77');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
 assert.equal(await page.locator('[data-rank="1"]').evaluate(el=>getComputedStyle(el).color),'rgb(17, 204, 119)');
 await page.getByLabel('Zvuk na konci klipu 5',{exact:true}).selectOption('mute');
 await page.getByRole('button',{name:'Poznámky podle klipů',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('input[aria-label="Poznámka u čísla 5"]')?.value==='Green block appears',{},{timeout:60000});
 assert.equal(await page.locator('.phone-rank-note').count(),1);
 await page.getByLabel('Náhled pozice 4',{exact:true}).click();assert.equal(await page.locator('.phone-rank-note').count(),2);
 await page.getByLabel('Náhled pozice 1',{exact:true}).click();assert.equal(await page.locator('.phone-rank-note').count(),5);
 await page.locator('.save-button').click();await page.reload();
 await page.waitForFunction(()=>document.querySelectorAll('.clip-thumb img').length===5);
 const state=await page.evaluate(()=>JSON.parse(localStorage.getItem('rank-studio-project')));
 assert.equal(state.layout.rank_colors['1'],'11CC77');assert.equal(state.clips[0].end_audio,'mute');assert.ok(state.clips.every(c=>c.rank_note==='Green block appears'&&c.rank_note_auto));
 assert.equal(state.maxDuration,25);assert.equal(state.searchDepth,'thorough');assert.equal(state.candidateCount,100);
 assert.ok(state.clips.every(c=>c.duration<=2.01&&c.visual_review.cut_audit.accepted&&c.has_audio));
 assert.ok(state.clips.reduce((sum,c)=>sum+c.duration,0)<11);
 await page.locator('#topic').scrollIntoViewIfNeeded();await page.screenshot({path:'.runtime/screenshots/highlights-studio-desktop.png',fullPage:false});
 for(const width of [2560,1920,1440,1100,900,720,390]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow ${width}`);if(width>=1920)assert.ok(await page.locator('main').evaluate(el=>Math.abs(el.getBoundingClientRect().right-innerWidth)<2),'Studio fills wide window');if(width===2560)await page.screenshot({path:'.runtime/screenshots/editor-full-width-2560.png',fullPage:false});}
 await page.getByLabel('Začátek klipu 5',{exact:true}).fill('0.1');
 assert.equal(await page.getByLabel('Poznámka u čísla 5',{exact:true}).inputValue(),'');
 assert.equal(await page.getByLabel('Poznámka u čísla 4',{exact:true}).inputValue(),'Green block appears');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'.runtime/screenshots/highlights-studio-mobile.png',fullPage:true});assert.deepEqual(errors,[]);
 console.log('Thorough highlights passed: all three sources, eight reviewed sources, actual short cuts/audio, 25s ceiling without padding, saved depth/limit, seven responsive widths, individual rank colors, clip-grounded note job/reveal/persistence and saved ending audio choice. AI/retrieval are protocol fixtures.');
} catch(error){console.error(logs);throw error;}finally{if(browser)await browser.close();server.kill('SIGTERM');}
