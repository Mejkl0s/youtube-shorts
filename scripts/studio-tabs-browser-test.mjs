// Real editor state and MP4 export across task panels; no external AI or TTS.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {chromium} from 'playwright';

const root=await mkdtemp(join(tmpdir(),'rank-studio-tabs-'));
const base='http://127.0.0.1:18809';
const env={...process.env,RANK_DATA_DIR:root,STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1'};
delete env.OPENAI_API_KEY;
const server=spawn('.venv/bin/python',['-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','18809','--log-level','error'],{env,stdio:['ignore','pipe','pipe']});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const tab=name=>page.getByRole('tab',{name,exact:true});
 await page.goto(base);
 await tab('Hledání').waitFor();
 assert.equal(await page.getByRole('tabpanel').count(),1);
 assert.equal(await page.locator('.search-options').evaluate(el=>el.open),false);
 assert.equal(await page.getByLabel('Vzhled nadpisu').isVisible(),false);
 assert.ok((await page.locator('body').innerText()).length<1500,'Initial screen should be concise');
 await page.locator('#topic').fill('winter fails');
 await tab('Hledání').press('End');assert.equal(await tab('AI').getAttribute('aria-selected'),'true');
 await tab('AI').press('Home');assert.equal(await tab('Hledání').getAttribute('aria-selected'),'true');
 assert.equal(await page.locator('#topic').inputValue(),'winter fails');
 await tab('Vzhled').click();await page.locator('#video-title').fill('Můj klidnější pracovní prostor');
 await page.getByLabel('Barevný režim čísel',{exact:true}).selectOption('individual');
 await tab('Zvuk').click();await page.getByRole('switch',{name:'AI voiceover',exact:true}).click();await page.getByRole('switch',{name:'Zvukové efekty',exact:true}).click();
 await tab('Klipy').click();
 await page.getByRole('button',{name:/Vyzkoušet syntetickou ukázku/}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.clip-thumb img').length===5,{},{timeout:60000});
 await page.getByLabel('Poznámka u čísla 5',{exact:true}).fill('Moje vlastní poznámka');
 await tab('Vzhled').click();assert.equal(await page.getByLabel('Barevný režim čísel',{exact:true}).inputValue(),'individual');
 await tab('Klipy').click();assert.equal(await page.getByLabel('Poznámka u čísla 5',{exact:true}).inputValue(),'Moje vlastní poznámka');
 await page.locator('#resolution').selectOption('720');
 await page.getByRole('button',{name:'Exportovat Short',exact:true}).click();
 await tab('Hledání').click();assert.equal(await page.locator('#topic').inputValue(),'winter fails');
 await page.getByRole('link',{name:'Stáhnout Short',exact:true}).waitFor({timeout:90000});
 const download=await page.request.get(new URL(await page.getByRole('link',{name:'Stáhnout Short',exact:true}).getAttribute('href'),base).href);
 assert.equal(download.status(),200);assert.ok((await download.body()).length>1000);
 await page.locator('.save-button').click();await page.reload();
 await tab('Klipy').click();assert.equal(await page.getByLabel('Poznámka u čísla 5',{exact:true}).inputValue(),'Moje vlastní poznámka');
 await mkdir('.runtime/screenshots',{recursive:true});
 for(const width of [1440,1100,900,600,400]){
  await page.setViewportSize({width,height:1000});
  for(const name of ['Hledání','Klipy','Vzhled','Zvuk','Projekt','AI']){
   await tab(name).click();
   assert.equal(await page.getByRole('tabpanel').count(),1);
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   if(overflow)console.log(await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.right>innerWidth+1;}).slice(0,12).map(el=>({tag:el.tagName,class:el.className,right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width}))));
   assert.equal(overflow,false,`Overflow in ${name} at ${width}`);
  }
 }
 await page.setViewportSize({width:1440,height:1000});await tab('Hledání').click();
 await page.screenshot({path:'.runtime/screenshots/studio-tabs-search.png'});
 await tab('Vzhled').click();await page.screenshot({path:'.runtime/screenshots/studio-tabs-appearance.png'});
 assert.deepEqual(errors,[]);
 console.log('Browser passed: six left tabs, one visible panel, keyboard navigation, retained drafts/settings, actual MP4 export while switching tabs, saved-project reload and every panel at 400–1440px.');
}catch(error){console.error(logs);throw error;}
finally{await browser?.close();server.kill('SIGTERM');await rm(root,{recursive:true,force:true});}
