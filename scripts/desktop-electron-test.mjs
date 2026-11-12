// Actual Electron main/preload, authenticated Python sidecar and persistent data.
// The model server below is a local protocol fixture, not a quality benchmark.
import {_electron as electron} from 'playwright';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {mkdir,readFile,stat} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
const require=createRequire(import.meta.url),executablePath=require('../desktop/node_modules/electron');
const root=resolve('.runtime/desktop-electron-'+randomUUID());await mkdir(root,{recursive:true});
const calls=[],timers=new Set();
const noteTexts=['Colors change direction','Shapes cross screen','Pattern shifts sideways','Blocks move together','Colors rotate again'];let noteIndex=0;
const modelServer=createServer(async(request,response)=>{
  let text='';for await(const part of request)text+=part;
  response.setHeader('content-type','application/json');
  if(request.url==='/v1/models')return response.end(JSON.stringify({data:[{id:'fixture-vision-a',capabilities:{vision:true}},{id:'fixture-vision-b',capabilities:{vision:true}},{id:'fixture-text',capabilities:{vision:false}}]}));
  if(request.url==='/v1/chat/completions'){
    const payload=JSON.parse(text);calls.push(payload);
    if(JSON.stringify(payload).includes('RANK NOTE REVIEW')){
      assert.ok(payload.messages.some(message=>Array.isArray(message.content)&&message.content.some(block=>block.type==='image_url')));
      return response.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({visible:true,note:noteTexts[noteIndex++%noteTexts.length]})}}]}));
    }
    if(JSON.stringify(payload).includes('SOUND DIRECTOR')){
      const blocks=payload.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]);
      assert.ok(blocks.some(b=>b.type==='image_url'));
      const verify=JSON.stringify(payload).includes('VERIFY.');
      const beats=verify?blocks.filter(b=>b.type==='text'&&b.text.startsWith('Candidate ')).map(b=>{const match=b.text.match(/^Candidate (\d+): (.*)\. Check actual/s),beat=JSON.parse(match[2]);return {candidate:Number(match[1]),accepted:true,time:beat.at,role:beat.role,effect:beat.kind,confidence:.96,observation:beat.observation};}):[
        {time:.7,role:'motion',effect:'whoosh',confidence:.96,observation:'Pattern moves.'},
        {time:1.4,role:'reveal',effect:'pop',confidence:.96,observation:'New pattern appears.'},
        {time:2.1,role:'stop',effect:'stop',confidence:.96,observation:'Pattern pauses.'},
        {time:3.2,role:'resolution',effect:'chime',confidence:.96,observation:'Result visible.'}];
      return response.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({beats})}}]}));
    }
    const slow=JSON.stringify(payload).includes('slow fixture');
    const timer=setTimeout(()=>{timers.delete(timer);response.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({text:'Fixture answer '+payload.model})}}]}));},slow?20000:900);
    timers.add(timer);response.on('close',()=>{clearTimeout(timer);timers.delete(timer);});return;
  }
  response.statusCode=404;response.end('{}');
});
await new Promise(resolve=>modelServer.listen(0,'127.0.0.1',resolve));
const endpoint=`http://127.0.0.1:${modelServer.address().port}/v1`;
let app;
async function launch(directory=root){
  app=await electron.launch({executablePath,args:[resolve('desktop'),...(process.platform==='linux'?['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']:[])],
    env:{...process.env,...(process.platform==='win32'&&process.env.RANK_DESKTOP_BACKEND?{TESSDATA_PREFIX:'rank-missing-fixture-language-directory'}:{}),RANK_DESKTOP_TEST_DATA:directory,XDG_CACHE_HOME:process.env.XDG_CACHE_HOME||resolve('.runtime/cache')},timeout:90000});
  const page=await app.firstWindow();await page.waitForURL(url=>url.protocol==='http:'&&url.hostname==='127.0.0.1',{timeout:90000});await page.locator('#video-title').waitFor({timeout:90000});return page;
}
async function quit(page){
  const closed=app.waitForEvent('close',{timeout:30000});
  await page.evaluate(()=>{window.rankDesktop.quit();});await closed;app=null;
}
async function checkSavedSearch(page,model){
  const health=await page.evaluate(async()=> (await fetch('/api/health')).json());
  const saved=await page.evaluate(async()=> (await fetch('/api/desktop/ai/config')).json());
  assert.equal(saved.active.model,model);assert.equal(saved.mode,'hybrid');assert.equal(saved.wizard_complete,true);
  const attempts=[];
  await page.route('**/api/health',route=>route.fulfill({json:{...health,local_vision:{...health.local_vision,ready:false}}}));
  await page.route('**/api/discover',route=>{attempts.push(route.request().postDataJSON());return route.fulfill({status:503,json:{detail:'Fixture search unavailable'}});});
  const response=page.waitForResponse(r=>r.url().endsWith('/api/health'));
  await page.evaluate(()=>window.dispatchEvent(new Event('rank-desktop-ai-changed')));await response;await page.waitForTimeout(80);
  await page.locator('#topic').fill('winter fails');
  for(let index=0;index<2;index++){
    await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Fixture search unavailable'}).waitFor();
    assert.equal(attempts.length,index+1);assert.equal(attempts[index].mode,'local');assert.equal(attempts[index].search_depth,'thorough');
    assert.equal(await page.getByRole('dialog').count(),0);
    const current=await page.evaluate(async()=> (await fetch('/api/desktop/ai/config')).json());
    assert.deepEqual(current.active,saved.active);assert.equal(current.mode,saved.mode);
    await page.getByRole('button',{name:'Zavřít chybu',exact:true}).click();
  }
  await page.unroute('**/api/discover');await page.unroute('**/api/health');
  const refreshed=page.waitForResponse(r=>r.url().endsWith('/api/health'));
  await page.evaluate(()=>window.dispatchEvent(new Event('rank-desktop-ai-changed')));await refreshed;
}

try{
  let page=await launch();const errors=[];page.on('pageerror',error=>errors.push(error.message));page.on('dialog',dialog=>dialog.accept());
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  const security=await app.evaluate(({BrowserWindow})=>{const p=BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();return {sandbox:p.sandbox,contextIsolation:p.contextIsolation,nodeIntegration:p.nodeIntegration};});
  assert.deepEqual(security,{sandbox:true,contextIsolation:true,nodeIntegration:false});
  assert.equal(await page.evaluate(()=>!!window.rankDesktop),true);
  assert.equal(await page.getByLabel('Rozsah hledání',{exact:true}).inputValue(),'thorough');
  assert.equal(await page.getByLabel('Počet kandidátů',{exact:true}).inputValue(),'100');
  assert.equal(await page.getByLabel('Maximální délka projektu',{exact:true}).inputValue(),'25');
  const origin=new URL(page.url()).origin;
  assert.equal((await fetch(origin+'/api/health')).status,403);
  assert.equal(await page.evaluate(async()=> (await fetch('/api/health')).status),200);
  const invalid=await page.evaluate(async()=>{const response=await fetch('/api/desktop/ai/providers/deepseek/key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'SECRET_FIXTURE_'.repeat(500)})});return {status:response.status,text:await response.text()};});
  assert.equal(invalid.status,422);assert.ok(!invalid.text.includes('SECRET_FIXTURE_'));
  const wizard=page.getByRole('dialog',{name:'Průvodce nastavením AI'});await wizard.waitFor();
  await mkdir('.runtime/screenshots',{recursive:true});await wizard.screenshot({path:'.runtime/screenshots/desktop-first-run.png'});
  await wizard.getByRole('button',{name:/Kombinovaný režim/}).click();
  await wizard.getByRole('button',{name:'Pokračovat',exact:true}).click();
  await wizard.getByRole('checkbox',{name:'Vlastní lokální API · lokální',exact:true}).check();
  await wizard.getByRole('checkbox',{name:'DeepSeek · cloud',exact:true}).check();
  await wizard.getByRole('button',{name:'Pokračovat',exact:true}).click();
  const local=wizard.locator('.desktop-provider-card').filter({has:page.getByText('Vlastní lokální API',{exact:true})});
  await local.getByLabel('Vlastní lokální API endpoint',{exact:true}).fill(endpoint);
  await local.getByRole('button',{name:'Uložit připojení',exact:true}).click();
  await local.getByRole('button',{name:'Ověřit a načíst modely',exact:true}).click();
  await local.getByText('Připojeno. Ověřeno 3 modelů.',{exact:true}).waitFor();
  const deepseek=wizard.locator('.desktop-provider-card').filter({has:page.getByText('DeepSeek',{exact:true})});
  await deepseek.getByLabel('DeepSeek API klíč',{exact:true}).fill('fixture-must-not-be-plaintext');
  await deepseek.getByRole('button',{name:'Uložit klíč',exact:true}).click();await deepseek.getByText('Klíč uložen.',{exact:true}).waitFor();
  await wizard.getByRole('button',{name:'Pokračovat',exact:true}).click();
  await page.getByLabel('settings poskytovatel AI',{exact:true}).selectOption('local');
  await page.getByLabel('settings model AI',{exact:true}).selectOption('fixture-text');
  assert.equal(await wizard.getByRole('button',{name:'Pokračovat',exact:true}).isDisabled(),true);
  await wizard.getByText(/Vybraný model nemá ověřenou podporu obrázků/).waitFor();
  await page.getByLabel('settings model AI',{exact:true}).selectOption('fixture-vision-b');
  assert.equal(await page.getByLabel('top model AI',{exact:true}).inputValue(),'fixture-vision-b');
  await wizard.getByRole('button',{name:'Pokračovat',exact:true}).click();
  await wizard.getByRole('button',{name:'Dokončit',exact:true}).click();await wizard.waitFor({state:'hidden'});
  const setup=page.getByRole('region',{name:'Výchozí nastavení AI'});
  await setup.getByText('Režim a model',{exact:true}).click();
  await setup.getByRole('button',{name:/Kombinovaný režim/}).click();
  assert.equal(await page.getByLabel('top model AI',{exact:true}).inputValue(),'fixture-vision-b');
  await setup.getByText('Režim a model',{exact:true}).click();

  const ocrHealth=await page.evaluate(async()=> (await fetch('/api/health')).json());
  if(process.platform==='win32'&&process.env.RANK_DESKTOP_BACKEND)assert.equal(ocrHealth.template_ocr_bundled,true);
  assert.equal(ocrHealth.template_ocr,true);
  const captionImage=root+'/caption.png',captionVideo=root+'/caption.mp4';
  const fixturePython=resolve('.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  execFileSync(fixturePython,['-c',`from PIL import Image,ImageDraw,ImageFont
import sys
im=Image.new('RGB',(720,1280),(15,25,75));d=ImageDraw.Draw(im);f=ImageFont.truetype(sys.argv[2],42)
d.text((50,290),'FUNNY KID FAILS',font=f,fill='white',stroke_width=2,stroke_fill='black')
for x in (530,598):
 d.ellipse((x-28,290,x+28,346),fill=(255,205,0),outline='black',width=2)
 d.ellipse((x-12,303,x-7,311),fill='black');d.ellipse((x+7,303,x+12,311),fill='black')
 d.arc((x-14,311,x+14,334),0,180,fill='black',width=3)
im.save(sys.argv[1])`,captionImage,resolve('backend/fonts/DejaVuSans-Bold.ttf')]);
  execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-loop','1','-i',captionImage,'-t','1','-r','15','-c:v','libx264','-pix_fmt','yuv420p',captionVideo]);
  const captionData=(await readFile(captionVideo)).toString('base64');
  const cleanup=await page.evaluate(async bytes=>{
    const data=Uint8Array.from(atob(bytes),c=>c.charCodeAt(0)),form=new FormData();form.append('file',new Blob([data],{type:'video/mp4'}),'caption.mp4');
    const upload=await fetch('/api/upload',{method:'POST',body:form});if(!upload.ok)throw Error('Fixture upload failed');const clip=await upload.json();
    const response=await fetch('/api/blur-suggestions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:clip.id,start:0,duration:1,framing:'fit'})});
    return {status:response.status,...await response.json()};
  },captionData);
  assert.equal(cleanup.status,200);for(const [x,y] of [[55,305],[450,326],[530,320],[622,340]])assert.ok(cleanup.regions.some(r=>r.x*720<=x&&(r.x+r.w)*720>=x&&r.y*1280<=y&&(r.y+r.h)*1280>=y));
  assert.ok(cleanup.regions.every(r=>r.h<=.075&&r.w*r.h<=.04));
  await checkSavedSearch(page,'fixture-vision-b');
  await page.getByLabel('top model AI',{exact:true}).selectOption('fixture-text');
  await page.locator('#topic').fill('winter fails');
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'podporu obrázků'}).waitFor();
  assert.equal(await page.getByRole('dialog').count(),0);
  await page.getByLabel('top model AI',{exact:true}).selectOption('fixture-vision-b');
  await page.getByRole('button',{name:'Zavřít chybu',exact:true}).click();
  const durationLimit=page.getByLabel('Maximální délka projektu',{exact:true});
  await durationLimit.fill('');await durationLimit.pressSequentially('40');await durationLimit.press('Tab');
  assert.equal(await durationLimit.inputValue(),'40');
  await durationLimit.fill('');await durationLimit.pressSequentially('25');await durationLimit.press('Tab');
  assert.equal(await durationLimit.inputValue(),'25');
  await page.getByText(/AI pomocník pro text ·/).click();
  await page.getByLabel('Zadání textovému AI pomocníkovi',{exact:true}).fill('Write a short original title.');
  await page.getByRole('button',{name:'Odeslat vybranému modelu',exact:true}).click();
  await page.getByRole('button',{name:'Zastavit odpověď',exact:true}).waitFor();
  await page.getByLabel('top model AI',{exact:true}).selectOption('fixture-vision-a');
  await page.locator('.desktop-text-result').filter({hasText:'Fixture answer fixture-vision-b'}).waitFor({timeout:20000});
  await page.getByRole('button',{name:'Odeslat vybranému modelu',exact:true}).click();
  await page.locator('.desktop-text-result').filter({hasText:'Fixture answer fixture-vision-a'}).waitFor({timeout:20000});
  await page.getByLabel('Zadání textovému AI pomocníkovi',{exact:true}).fill('slow fixture');
  await page.getByRole('button',{name:'Odeslat vybranému modelu',exact:true}).click();
  await page.getByRole('button',{name:'Zastavit odpověď',exact:true}).click();
  await page.getByRole('button',{name:'Zastavit odpověď',exact:true}).waitFor({state:'hidden',timeout:10000});
  await page.getByRole('button',{name:'Pokročilé nastavení AI',exact:true}).click();
  const settings=page.getByRole('dialog',{name:'Nastavení aplikace'});await settings.waitFor();
  assert.equal(await page.getByLabel('settings model AI',{exact:true}).inputValue(),'fixture-vision-a');
  await settings.screenshot({path:'.runtime/screenshots/desktop-models.png'});
  await settings.getByRole('button',{name:'Aktualizace',exact:true}).click();
  assert.equal(await settings.getByRole('button',{name:'Zkontrolovat aktualizace',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Zavřít nastavení',exact:true}).click();
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1100,800));
  for(const width of [900,1100,1440]){
    await app.evaluate(({BrowserWindow},w)=>BrowserWindow.getAllWindows()[0].setSize(w,800),width);
    await page.waitForTimeout(150);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Native overflow at ${width}`);
    assert.ok(await page.evaluate(()=>{
      const top=document.querySelector('.topbar').getBoundingClientRect();
      return parseFloat(getComputedStyle(document.querySelector('.preview-panel')).top)>=top.height+10;
    }),`Preview behind native toolbar at ${width}`);
  }
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1100,800));
  await page.evaluate(()=>{Object.defineProperty(navigator,'onLine',{value:false,configurable:true});window.dispatchEvent(new Event('offline'));});
  await page.getByText('Offline',{exact:true}).waitFor();
  await page.getByLabel('Zadání textovému AI pomocníkovi',{exact:true}).fill('Local work while remote connectivity is unavailable.');
  await page.getByRole('button',{name:'Odeslat vybranému modelu',exact:true}).click();
  await page.locator('.desktop-text-result').filter({hasText:'Fixture answer fixture-vision-a'}).waitFor({timeout:20000});
  await page.getByRole('button',{name:/Vyzkoušet syntetickou ukázku/}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.clip-thumb img').length===5,{},{timeout:60000});
  assert.equal(await page.getByLabel('Poznámka u čísla 5',{exact:true}).inputValue(),'');
  await page.getByRole('button',{name:'Poznámky podle klipů',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('input[aria-label="Poznámka u čísla 1"]')?.value==='Colors rotate again',{},{timeout:60000});
  for(let index=0;index<5;index++)assert.equal(await page.getByLabel(`Poznámka u čísla ${5-index}`,{exact:true}).inputValue(),noteTexts[index]);
  assert.equal(await page.locator('.phone-rank-note').count(),1);
  await page.getByLabel('Náhled pozice 4',{exact:true}).click();assert.equal(await page.locator('.phone-rank-note').count(),2);
  await page.getByLabel('Barevný režim čísel',{exact:true}).selectOption('individual');
  await page.getByLabel('Barva čísla 1',{exact:true}).evaluate(el=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'#11cc77');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(await page.locator('[data-rank="1"]').evaluate(el=>getComputedStyle(el).color),'rgb(17, 204, 119)');
  await page.getByLabel('Voiceover',{exact:true}).uncheck();
  await page.getByLabel('Načasování efektů klipu 5',{exact:true}).selectOption('manual');
  await page.getByLabel('Moment efektu klipu 5',{exact:true}).fill('1.7');
  await page.locator('#resolution').selectOption('720');
  const videoFile=root+'/native-export.mp4';
  await app.evaluate(({dialog},file)=>{dialog.showSaveDialogSync=()=>file;},videoFile);
  await page.getByRole('button',{name:'Exportovat Short',exact:true}).click();
  await page.getByRole('link',{name:'Stáhnout Short',exact:true}).waitFor({timeout:90000});
  await page.getByText('Časování efektů',{exact:true}).click();
  assert.ok((await page.locator('.effects-timeline').innerText()).includes('Překvapení · pop'));
  const soundPlan=await page.evaluate(async()=>{const jobs=await fetch('/api/jobs/'+document.querySelector('a.export-button').getAttribute('href').split('/').at(-2));return (await jobs.json()).effects_plan;});
  assert.ok(soundPlan.some(p=>p.source==='director'&&p.events.length>2));
  await page.getByRole('link',{name:'Stáhnout Short',exact:true}).click();
  for(let attempt=0;attempt<900;attempt++){try{if((await stat(videoFile)).size>1000)break;}catch{}await new Promise(resolve=>setTimeout(resolve,100));}
  // Wait for the native DownloadItem to finish before probing its container.
  let probe;
  for(let attempt=0;attempt<40;attempt++){try{probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',videoFile],{stdio:['ignore','pipe','ignore']}).toString());break;}catch{await new Promise(resolve=>setTimeout(resolve,200));}}
  assert.ok(probe&&Number(probe.format.duration)<=25.000001);assert.ok(probe.streams.some(stream=>stream.codec_type==='audio'));
  await page.getByRole('button',{name:'Upravit plán klipu #4',exact:true}).click();
  assert.equal(await page.getByLabel('Načasování efektů klipu 4',{exact:true}).inputValue(),'custom');
  await page.getByLabel('Typ efektu 1 klipu 4',{exact:true}).selectOption('rise');
  await page.locator('#video-title').fill('Desktop project restored');
  const projectFile=root+'/portable.rankstudio';
  await app.evaluate(({dialog},file)=>{dialog.showSaveDialog=async()=>({canceled:false,filePath:file});dialog.showOpenDialog=async()=>({canceled:false,filePaths:[file]});},projectFile);
  await page.getByRole('button',{name:'Export projektu',exact:true}).click();
  await page.getByText('Projekt exportován.',{exact:true}).waitFor({timeout:60000});
  assert.ok((await stat(projectFile)).size>1000);
  // A failed target-state commit must leave the original editor and autosave
  // usable. SQLite injects a real storage failure for this import only.
  const python=resolve('.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  const database=root+'/runtime/private/desktop/projects.sqlite3';
  function sql(statement){return execFileSync(python,['-X','utf8','-c','import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);db.execute(sys.argv[2]);db.commit();db.close()',database,statement]);}
  await page.locator('#video-title').fill('Keep current project after failed import');
  await page.evaluate(()=>window.rankDesktop.saveState(Object.fromEntries(['rank-studio-project','rank-studio-chat','rank-studio-assets','rank-studio-sources','rank-studio-previous-clips','rank-studio-writing'].map(key=>[key,localStorage.getItem(key)]).filter(([,value])=>value!==null))));
  sql("CREATE TRIGGER reject_fixture_import BEFORE INSERT ON state WHEN NEW.key='rank-studio-project' AND instr(NEW.value,'Desktop project restored')>0 BEGIN SELECT RAISE(FAIL,'fixture storage failure'); END");
  await page.getByRole('button',{name:'Import projektu',exact:true}).click();
  await page.locator('.project-import-progress').waitFor({state:'hidden',timeout:60000});
  assert.equal(await page.locator('#video-title').inputValue(),'Keep current project after failed import');
  await page.locator('#video-title').fill('Autosave still works after failed import');
  let retained='';
  for(let attempt=0;attempt<40;attempt++){
    retained=execFileSync(python,['-X','utf8','-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);print(db.execute(\"SELECT value FROM state WHERE key='rank-studio-project'\").fetchone()[0]);db.close()",database],{encoding:'utf8'});
    if(retained.includes('Autosave still works after failed import'))break;
    await page.waitForTimeout(250);
  }
  assert.ok(retained.includes('Autosave still works after failed import'));
  sql('DROP TRIGGER reject_fixture_import');
  const imported=page.waitForEvent('domcontentloaded');
  await page.getByRole('button',{name:'Import projektu',exact:true}).click();
  await imported;
  await page.waitForFunction(()=>document.querySelector('#video-title')?.value==='Desktop project restored',{},{timeout:60000});
  await page.screenshot({path:'.runtime/screenshots/desktop-editor.png',fullPage:false});
  // Quit immediately after editing: pending debounce must not lose the last edit.
  await page.locator('#video-title').fill('Desktop project immediate save');
  await quit(page);
  const config=await readFile(root+'/runtime/private/desktop/ai.json','utf8');assert.ok(!config.includes('fixture-must-not-be-plaintext'));
  if(process.platform==='win32'){const vault=await readFile(root+'/runtime/private/desktop/credentials.dpapi.json');assert.ok(!vault.includes(Buffer.from('fixture-must-not-be-plaintext')));}
  page=await launch();page.on('pageerror',error=>errors.push(error.message));page.on('dialog',dialog=>dialog.accept());
  assert.equal(await page.getByRole('dialog',{name:'Průvodce nastavením AI'}).count(),0);
  await page.waitForFunction(()=>document.querySelector('#video-title')?.value==='Desktop project immediate save');
  assert.equal(await page.getByLabel('top model AI',{exact:true}).inputValue(),'fixture-vision-a');
  assert.equal(await page.getByLabel('Načasování efektů klipu 5',{exact:true}).inputValue(),'manual');
  assert.equal(await page.getByLabel('Moment efektu klipu 5',{exact:true}).inputValue(),'1.7');
  assert.equal(await page.getByLabel('Načasování efektů klipu 4',{exact:true}).inputValue(),'custom');
  assert.equal(await page.getByLabel('Typ efektu 1 klipu 4',{exact:true}).inputValue(),'rise');
  assert.equal(await page.getByLabel('Barevný režim čísel',{exact:true}).inputValue(),'individual');
  assert.equal(await page.getByLabel('Barva čísla 1',{exact:true}).inputValue(),'#11cc77');
  assert.equal(await page.getByLabel('Poznámka u čísla 5',{exact:true}).inputValue(),noteTexts[0]);
  await checkSavedSearch(page,'fixture-vision-a');
  await page.getByRole('button',{name:'Pokročilé nastavení AI',exact:true}).click();
  await page.getByRole('button',{name:'Spustit průvodce nastavením',exact:true}).click();await page.getByRole('dialog',{name:'Průvodce nastavením AI'}).waitFor();
  assert.equal(await page.getByRole('button',{name:/Kombinovaný režim/}).getAttribute('class'),'selected');
  await page.getByRole('button',{name:'Zavřít nastavení',exact:true}).click();
  const prefs=await page.evaluate(()=>window.rankDesktop.info());
  await page.evaluate(settings=>window.rankDesktop.preferences({...settings,closeBehavior:'tray'}),prefs.settings);
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].close());
  assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isVisible()),false);
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].show());
  await page.evaluate(settings=>window.rankDesktop.preferences({...settings,closeBehavior:'quit'}),prefs.settings);
  await quit(page);assert.ok(calls.length>=3);
  const technicalRoot=root+'-without-ai';
  page=await launch(technicalRoot);page.on('pageerror',error=>errors.push(error.message));
  const technicalWizard=page.getByRole('dialog',{name:'Průvodce nastavením AI'});await technicalWizard.waitFor();
  await technicalWizard.getByRole('button',{name:'Pokračovat bez obrazové AI',exact:true}).click();
  await technicalWizard.waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.querySelector('#search-mode')?.value==='free'&&document.querySelector('[aria-label="Rozsah hledání"]')?.value==='quick');
  await quit(page);page=await launch(technicalRoot);page.on('pageerror',error=>errors.push(error.message));
  assert.equal(await page.getByRole('dialog').count(),0);
  assert.equal(await page.locator('#search-mode').inputValue(),'free');
  assert.equal(await page.getByLabel('Rozsah hledání',{exact:true}).inputValue(),'quick');
  const technicalAttempts=[];
  await page.route('**/api/discover',route=>{technicalAttempts.push(route.request().postDataJSON());return route.fulfill({status:503,json:{detail:'Fixture technical search unavailable'}});});
  await page.locator('#topic').fill('winter fails');
  for(let index=0;index<2;index++){
    await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Fixture technical search unavailable'}).waitFor();
    assert.equal(technicalAttempts[index].mode,'free');assert.equal(technicalAttempts[index].search_depth,'quick');
    assert.equal(await page.getByRole('dialog').count(),0);
    await page.getByRole('button',{name:'Zavřít chybu',exact:true}).click();
  }
  await quit(page);assert.deepEqual(errors,[]);
  console.log('Actual Electron passed: isolated preload, token authentication, wizard/hybrid configuration, provider discovery, saved search without repeated settings (also after restart and with stale health), upfront vision validation, live model switching with per-job snapshot, cancellation, local work with offline UI, bundled OCR with isolated language path and complete titles/emoji, contextual notes per actual cut, individual rank colors, MP4/archive export, immediate-close persistence, restart, repeat wizard and tray close behavior. AI replies were local fixtures. Windows installer/signature verification is a separate native acceptance check.');
}finally{
  if(app){try{await app.evaluate(({app})=>app.exit(1));}catch{}}
  for(const timer of timers)clearTimeout(timer);modelServer.closeAllConnections();await new Promise(resolve=>modelServer.close(resolve));
}
