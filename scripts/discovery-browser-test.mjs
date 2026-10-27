// Actual discovery/scene selection and MP4 mix with local fixture search and speech.
// No external search, paid AI or live speech service is called.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {execFileSync,spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createServer} from 'node:net';
import {randomUUID} from 'node:crypto';
const root=resolve('.runtime/discovery-test-'+randomUUID());
await mkdir(root,{recursive:true});
for(const [i,duration] of [3,5,7,9,12].entries())execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y',
  '-f','lavfi','-i',`color=c=gray:s=160x284:r=15:d=${duration}`,'-f','lavfi','-i',`sine=frequency=440:sample_rate=44100:duration=${duration}`,
  '-vf',`drawbox=x=10:y=100:w=30:h=50:color=lime:t=fill:enable='gte(t,${duration-1})'`,'-c:v','libx264','-c:a','aac',`${root}/fixture-${i}.mp4`]);
const reservation=createServer();await new Promise(done=>reservation.listen(0,'127.0.0.1',done));
const port=reservation.address().port;await new Promise(done=>reservation.close(done));
const base=`http://127.0.0.1:${port}`;
const code=`
import sys,shutil,uuid,wave
from pathlib import Path
import numpy as np
from backend import main as m
root=Path(sys.argv[1])
def search(topic,allow,limit,only=False,exclude=()):
 seen={m.canonical_url(u) for u in exclude}
 rows=[{'url':f'https://www.youtube.com/shorts/NEWSNOW{i:04d}','title':f'Winter fails {i}','source':'YouTube'} for i in range(10)]
 return [r for r in rows if m.canonical_url(r['url']) not in seen][:5],[]
def download(item):
 i=int(item['url'][-4:]);identity=uuid.uuid4().hex;folder=m.DATA/'media'/identity;folder.mkdir()
 shutil.copyfile(root/f'fixture-{i%5}.mp4',folder/'source')
 return {**m.register(folder/'source',identity,item['title']),'source_url':item['url'],'source':'YouTube'}
def speech(text,language,output,config=None):
 if (root/'speech-down').exists():raise ValueError('Fixture speech service unavailable')
 rate=24000;t=np.arange(int(rate*.7))/rate
 with wave.open(str(output),'wb') as f:
  f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes((np.sin(2*np.pi*1200*t)*12000).astype('<i2').tobytes())
m.public_search=search;m.youtube_search=lambda *args:([],[]);m.download_candidate=download;m.synthesize=speech
import uvicorn
uvicorn.run(m.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
`;
const env={...process.env,RANK_DATA_DIR:root+'/data',STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1'};
delete env.OPENAI_API_KEY;delete env.ELEVENLABS_API_KEY;
const server=spawn('.venv/bin/python',['-c',code,root,String(port)],{env,stdio:['ignore','pipe','pipe']});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
let browser;
try{
  for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[],searches=[],renders=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  page.on('request',r=>{if(r.method()==='POST'){if(r.url().endsWith('/api/discover'))searches.push(r.postDataJSON());if(r.url().endsWith('/api/render'))renders.push(r.postDataJSON());}});
  await page.goto(base);
  await page.locator('#topic').fill('ranking funniest winter fails');
  await page.getByLabel('Automaticky rozmazat nalezený text ve zdrojových klipech').uncheck();
  await page.locator('#resolution').selectOption('720');
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  const player=page.getByLabel('Přehrávač hotového Shortu',{exact:true});
  await player.waitFor({timeout:120000});
  await page.waitForFunction(()=>document.querySelector('.finished-preview video')?.readyState>=1);
  assert.equal(renders.length,1);assert.equal(renders[0].voice,true);assert.equal(renders[0].effects,true);
  assert.deepEqual(new Set(renders[0].clips.map(c=>Math.round(c.duration))),new Set([3,5,7,9,12]));
  assert.deepEqual(renders[0].clips.map(c=>c.voiceover),['Number five.','Number four.','Number three.','Number two.','Number one.']);
  const first=(await page.request.get(new URL(await player.getAttribute('src'),base).href)).body();
  const firstFile=root+'/with-voice.mp4';await writeFile(firstFile,await first);
  const oldIds=renders[0].clips.map(c=>c.id),oldSources=renders[0].clips.map(c=>c.source_url);
  assert.ok(oldSources.every(Boolean));
  await page.getByLabel('Voiceover',{exact:true}).uncheck();
  await page.getByLabel('Sound efekty',{exact:true}).uncheck();
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.finished-preview'));
  await player.waitFor({timeout:120000});
  assert.equal(renders.length,2);assert.equal(renders[1].voice,false);assert.equal(renders[1].effects,false);
  assert.ok(searches[1].exclude_urls.length>=5);assert.ok(searches[1].exclude_asset_ids.length>=5);
  assert.ok(renders[1].clips.every(c=>!oldSources.includes(c.source_url)&&!oldIds.includes(c.id)));
  const secondFile=root+'/original-only.mp4';await writeFile(secondFile,await (await page.request.get(new URL(await player.getAttribute('src'),base).href)).body());
  const spectral=`import sys,numpy as np,subprocess
for p in sys.argv[1:]:
 raw=subprocess.check_output(['ffmpeg','-v','error','-ss','0.55','-i',p,'-t','0.3','-vn','-ar','24000','-ac','1','-f','s16le','pipe:1'])
 x=np.frombuffer(raw,dtype='<i2').astype(float);s=abs(np.fft.rfft(x*np.hanning(len(x))));freq=np.fft.rfftfreq(len(x),1/24000)
 print(float(s[abs(freq-1200)<20].max()/s[abs(freq-440)<20].max()))`;
  const ratios=execFileSync('.venv/bin/python',['-c',spectral,firstFile,secondFile],{encoding:'utf8'}).trim().split('\n').map(Number);
  assert.ok(ratios[0]>.5&&ratios[1]<.01,JSON.stringify(ratios));
  // A full editor must not make a failed repeat search look successful.
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Předchozí klipy jsou uložené zvlášť'}).waitFor({timeout:120000});
  assert.equal(renders.length,2);
  const secondIds=renders[1].clips.map(c=>c.id);
  assert.equal(await page.locator('.ready-label').count(),0);
  assert.equal(await page.getByRole('button',{name:'Exportovat Short',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Vrátit předchozí klipy',exact:true}).click();
  await page.locator('.save-button').click();
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('rank-studio-project')).clips.map(c=>c.id)),secondIds);
  await page.reload();
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Předchozí klipy jsou uložené zvlášť'}).waitFor({timeout:120000});
  assert.ok(searches.at(-1).exclude_urls.length>=10);assert.equal(await page.locator('.ready-label').count(),0);assert.equal(renders.length,2);
  await page.getByLabel('Vynechat dříve použité zdroje').uncheck();
  await page.getByLabel('Po hledání vytvořit hotový náhled').uncheck();
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.ready-label').length===5&&document.querySelector('.toast')?.textContent.includes('Klipy jsou připravené'),{},{timeout:120000});
  assert.equal(searches.at(-1).exclude_urls.length,0);assert.equal(renders.length,2);
  // A speech provider failure must retain the newly found clips and settings.
  await writeFile(root+'/speech-down','1');
  await page.getByLabel('Po hledání vytvořit hotový náhled').check();
  await page.getByLabel('Voiceover',{exact:true}).check();
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Fixture speech service unavailable'}).waitFor({timeout:120000});
  assert.equal(renders.length,3);assert.equal(await page.locator('.ready-label').count(),5);
  assert.equal(await page.getByLabel('Voiceover',{exact:true}).isChecked(),true);
  assert.equal(await player.count(),0);
  await mkdir('.runtime/screenshots',{recursive:true});
  await page.locator('.topic-box').screenshot({path:'.runtime/screenshots/discovery-options.png'});
  assert.deepEqual(errors,[]);
  console.log('Discovery browser passed: actual scene lengths 3–12s, automatic mixed MP4, real voice frequency present/absent, independent voice/SFX/preview switches, 10 unique source clips, persistent exclusions, opt-in reuse and a separate recoverable backup on zero results. External search and speech were replaced by local fixtures.');
}catch(error){console.error(logs);throw error;}finally{if(browser)await browser.close();server.kill('SIGTERM');}
