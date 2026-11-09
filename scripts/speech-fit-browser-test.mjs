// Real browser -> render API -> MP4 with padded TTS protocol fixtures.
// No external TTS request and no claim about actual model/voice quality.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {execFileSync,spawn} from 'node:child_process';
import {mkdir,readFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
const root=resolve('.runtime/speech-browser-'+randomUUID());await mkdir(root,{recursive:true});
const reservation=createServer();await new Promise(done=>reservation.listen(0,'127.0.0.1',done));const port=reservation.address().port;await new Promise(done=>reservation.close(done));
const code=`
import sys,json,wave,numpy as np
from pathlib import Path
from backend import main as m
root=Path(sys.argv[1]);calls=[]
def speech(text,language,path,config=None):
 calls.append(text);(root/'calls.json').write_text(json.dumps(calls))
 rate=24000;seconds=1.5 if text=='Number four.' else .45 if text=='Four.' else .85
 tone=(np.sin(2*np.pi*440*np.arange(round(rate*seconds))/rate)*6000).astype('<i2')
 data=np.concatenate([np.zeros(round(rate*.6),dtype='<i2'),tone,np.zeros(round(rate*1.2),dtype='<i2')])
 with wave.open(str(path),'wb') as out:
  out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(data.tobytes())
m.synthesize=speech
import uvicorn
uvicorn.run(m.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
`;
const env={...process.env,RANK_DATA_DIR:root+'/data',STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1',RANK_FREE_ONLY:'1'};delete env.OPENAI_API_KEY;delete env.ELEVENLABS_API_KEY;delete env.RANK_DESKTOP_MODE;
const server=spawn('.venv/bin/python',['-c',code,root,String(port)],{env,stdio:['ignore','pipe','pipe']});let logs='',browser;server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
try{
 const base=`http://127.0.0.1:${port}`;
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await new Promise(done=>setTimeout(done,100));}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',dialog=>dialog.accept());
 await page.goto(base);await page.getByRole('button',{name:/Vyzkoušet syntetickou ukázku/}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.clip-thumb img').length===5,{},{timeout:60000});
 for(const [index,seconds] of [4.1,1,2,1.2,2].entries())await page.getByLabel(`Délka klipu ${5-index}`,{exact:true}).fill(String(seconds));
 await page.getByRole('button',{name:'Uvedení pořadí zdarma',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('input[aria-label="Voiceover klipu 4"]')?.value==='Number four.');
 await page.locator('#resolution').selectOption('720');
 await page.getByRole('switch',{name:'AI voiceover',exact:true}).check();await page.getByRole('switch',{name:'Zvukové efekty',exact:true}).check();
 await page.getByRole('button',{name:'Vytvořit náhled se zvukem',exact:true}).click();
 const finished=page.getByRole('region',{name:'Hotové video',exact:true});await finished.waitFor({timeout:90000});
 await page.getByRole('status').filter({hasText:'Four.'}).waitFor();
 const url=await page.getByLabel('Přehrávač hotového Shortu',{exact:true}).getAttribute('src');
 const response=await fetch(base+url);assert.equal(response.status,200);
 const file=root+'/preview.mp4';await (await import('node:fs/promises')).writeFile(file,Buffer.from(await response.arrayBuffer()));
 const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',file]));
 assert.ok(Math.abs(Number(probe.format.duration)-10.3)<.08);assert.ok(probe.streams.some(s=>s.codec_type==='audio'));
 const pcm=execFileSync('ffmpeg',['-v','error','-i',file,'-vn','-ac','1','-ar','24000','-f','s16le','pipe:1']);
 const amplitude=(start,end)=>{let total=0,count=0;for(let at=Math.round(start*24000)*2;at<Math.round(end*24000)*2;at+=2){total+=Math.abs(pcm.readInt16LE(at));count++;}return total/count;};
 assert.ok(amplitude(4.12,4.22)>100);assert.ok(amplitude(4.6,4.8)>300);
 assert.deepEqual(JSON.parse(await readFile(root+'/calls.json','utf8')),['Number five.','Number four.','Four.','Number three.','Number two.','Number one.']);
 assert.equal(await page.getByRole('alert').count(),0);assert.deepEqual(errors,[]);
 await mkdir('.runtime/screenshots',{recursive:true});await finished.screenshot({path:'.runtime/screenshots/speech-fit-preview.png'});
 console.log('Voice + SFX preview passed: real browser/render/MP4, padded speech, one-second #4, compact announcement warning, original 10.3s duration and audible tracks. TTS is a protocol fixture.');
}catch(error){console.error(logs);throw error;}finally{if(browser)await browser.close();server.kill('SIGTERM');}
