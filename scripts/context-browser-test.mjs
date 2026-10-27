import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdir,readFile} from 'node:fs/promises';

const base=process.env.TEST_BASE_URL||'http://127.0.0.1:8000';
await mkdir('.runtime/screenshots',{recursive:true});
const file='.runtime/screenshots/context-fixture.mp4';
execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=gray:s=320x180:r=15:d=12',
  '-f','lavfi','-i','sine=frequency=440:sample_rate=44100:duration=12','-vf',"drawbox=x=0:y=40:w=30:h=60:color=lime:t=fill:enable='gte(t,10.5)'",'-c:v','libx264','-c:a','aac',file]);
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',error=>errors.push(error.message));
page.on('dialog',dialog=>dialog.accept());
try{
  await page.goto(base);
  const clips=[];
  for(let i=0;i<5;i++){
    const upload=await page.request.post(base+'/api/upload',{multipart:{file:{name:'Late point.mp4',mimeType:'video/mp4',buffer:await readFile(file)}}});
    assert.equal(upload.status(),200);
    const source=await upload.json();
    const response=await page.request.post(base+'/api/clip-cut',{data:{id:source.id,start:0,duration:4,cut_start:2,cut_end:6,framing:'fill'}});
    assert.equal(response.status(),200);
    clips.push({...await response.json(),start:0,sourceDuration:4,duration:4,selection_version:null,title:'My moment',rank_note:'My custom note',voiceover:''});
  }
  await page.evaluate(clips=>localStorage.setItem('rank-studio-project',JSON.stringify({clips,title:'WINTER FAILS',voice:false,effects:true,captions:true,originalVolume:.12})),clips);
  await page.reload();
  await page.getByRole('textbox',{name:'Voiceover klipu 5',exact:true}).waitFor();
  await page.getByText('Tento projekt stále používá pět čtyřsekundových výřezů.',{exact:true}).waitFor();
  const original=page.locator('label.volume-slider').filter({hasText:'Původní zvuk'}).locator('input');
  assert.equal(await original.inputValue(),'0.8');
  await original.focus();await original.press('End');
  assert.equal(await original.inputValue(),'1.5');
  assert.equal(await page.locator('.phone>video').evaluate(video=>video.volume),1);
  // Restore the saved 80% mix before rendering.
  await page.reload();
  await page.getByRole('button',{name:'Znovu vybrat celé scény',exact:true}).click();
  await page.waitForFunction(()=>Number(document.querySelector('[aria-label="Délka klipu 5"]')?.value)>11.9,{},{timeout:120000});
  assert.equal(await page.getByRole('textbox',{name:'Poznámka u čísla 5',exact:true}).inputValue(),'My custom note');
  assert.equal(await page.locator('.phone>video').evaluate(video=>getComputedStyle(video).objectFit),'contain');
  await page.getByRole('button',{name:'Obměnit poznámky',exact:true}).click();
  await page.waitForFunction(()=>new Set([...document.querySelectorAll('[aria-label^="Poznámka u čísla"]')].map(e=>e.value)).size===5);
  const first=await page.locator('[aria-label^="Poznámka u čísla"]').evaluateAll(els=>els.map(el=>el.value));
  await page.getByRole('button',{name:'Obměnit poznámky',exact:true}).click();
  await page.waitForFunction(previous=>[...document.querySelectorAll('[aria-label^="Poznámka u čísla"]')].every(el=>!previous.includes(el.value)),first);
  const note=await page.getByRole('textbox',{name:'Poznámka u čísla 5',exact:true}).inputValue();
  await page.locator('.clip-card').first().getByRole('button',{name:'Upravit střih',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Upravit střih a pointu',exact:true});
  await dialog.waitFor();
  assert.equal(await dialog.getByLabel('Konec výřezu',{exact:true}).inputValue(),'12');
  await dialog.getByLabel('Začátek výřezu',{exact:true}).fill('8');
  await dialog.screenshot({path:'.runtime/screenshots/context-trimmer.png'});
  await dialog.getByRole('button',{name:'Použít střih',exact:true}).click();
  await dialog.waitFor({state:'hidden',timeout:60000});
  assert.ok(Number(await page.getByLabel('Délka klipu 5',{exact:true}).inputValue())<=4.1);
  assert.equal(await page.getByRole('textbox',{name:'Poznámka u čísla 5',exact:true}).inputValue(),note);
  // Shorten the other test clips only to keep this actual audio export fast.
  for(const rank of [1,2,3,4])await page.getByLabel(`Délka klipu ${rank}`,{exact:true}).fill('2');
  let payload;
  page.on('request',request=>{if(request.url().endsWith('/api/render'))payload=request.postDataJSON();});
  await page.getByRole('button',{name:'Vytvořit náhled se zvukem',exact:true}).click();
  const finished=page.getByRole('region',{name:'Hotové video',exact:true});
  await finished.waitFor({timeout:120000});
  const player=page.getByLabel('Přehrávač hotového Shortu',{exact:true});
  await page.waitForFunction(()=>document.querySelector('.finished-preview video')?.readyState>=1);
  assert.equal(payload.original_volume,.8);assert.equal(payload.effects,true);assert.equal(payload.voice,false);
  assert.ok(await player.evaluate(video=>video.duration)>10);
  assert.equal(await page.getByRole('link',{name:'Stáhnout Short',exact:true}).count(),1);
  await page.getByRole('button',{name:'Připravit voiceover zdarma',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Voiceover klipu 5"]')?.value==='Number five.');
  assert.equal(await page.getByRole('switch',{name:'AI voiceover',exact:true}).getAttribute('aria-checked'),'true');
  assert.equal(await page.getByRole('textbox',{name:'Poznámka u čísla 5',exact:true}).inputValue(),note);
  await page.setViewportSize({width:390,height:844});
  await page.locator('.clip-card').first().getByRole('button',{name:'Upravit střih',exact:true}).click();
  await page.getByRole('dialog').screenshot({path:'.runtime/screenshots/context-trimmer-mobile.png'});
  assert.deepEqual(errors,[]);
  console.log('Context browser checks passed: legacy four-second cuts restored, complete frame, louder original audio, gain bounds, varied persistent notes, original-footage trimmer, real sound preview/export and explicit free voice preparation. Live speech service not exercised.');
}finally{await browser.close();}
