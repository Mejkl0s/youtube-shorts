import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {chromium} from 'playwright';

const root=await mkdtemp(join(tmpdir(),'rank-social-browser-'));
const base='http://127.0.0.1:18799';
const code=`
from backend import main as m
def discover(identity,body):
 m.set_job(identity,status='failed',progress=100,message='Načtena dvě videa, další zdroje jsou omezené.',
  source_stats={'TikTok':{'found':4,'downloaded':0,'failed':2},'Instagram':{'found':0,'downloaded':0,'failed':0},'YouTube':{'found':2,'downloaded':2,'failed':0}},
  search_results=[],partial_clips=[],download_failures=[{'source':'TikTok','url':'https://www.tiktok.com/@fixture/video/123','kind':'login_required','reason':'Síť vyžaduje přihlášenou relaci.'}],
  warnings=['Instagram: vyhledávače nevrátily žádný odpovídající odkaz na video.'])
m.discover=discover
import uvicorn
uvicorn.run(m.app,host='127.0.0.1',port=18799,log_level='error')
`;
const env={...process.env,RANK_DATA_DIR:root,STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1'};
delete env.OPENAI_API_KEY;
const server=spawn('.venv/bin/python',['-c',code],{env,stdio:['ignore','pipe','pipe']});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
let browser;
try{
 for(let i=0;i<100;i++){
  try{if((await fetch(base+'/api/health')).ok)break;}catch{}
  await new Promise(r=>setTimeout(r,100));
 }
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];let request;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().endsWith('/api/discover')&&r.method()==='POST')request=r.postDataJSON();});
 await page.goto(base);
 await page.locator('#topic').fill('kids fails');
 await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
 const diagnostics=page.getByLabel('Výsledky jednotlivých zdrojů');
 await diagnostics.getByText('Síť vyžaduje přihlášenou relaci.',{exact:true}).waitFor();
 assert.equal(await diagnostics.locator('[data-source]').count(),3);
 await diagnostics.locator('[data-source="Instagram"]').getByText('Žádné odpovídající odkazy ve veřejném indexu.',{exact:false}).waitFor();
 await diagnostics.getByRole('button',{name:'Přihlášení ke zdrojům',exact:true}).click();
 assert.equal(await page.locator('.source-sessions').evaluate(el=>el.open),true);
 assert.equal(request.allow_youtube,true);
 assert.deepEqual(errors,[]);
 console.log('Browser passed: all three source cards, visible Instagram index miss, TikTok login reason and session-panel shortcut. Search replies were fixtures.');
}catch(error){console.error(logs);throw error;}
finally{await browser?.close();server.kill('SIGTERM');await rm(root,{recursive:true,force:true});}
