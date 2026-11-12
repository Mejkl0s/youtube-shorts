// Actual video decoding, two-pass evidence, cuts and browser review workflow.
// Only search, downloading and the remote vision response use local fixtures.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {execFileSync,spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createServer} from 'node:net';
import {randomUUID} from 'node:crypto';
const root=resolve('.runtime/visual-browser-'+randomUUID());
await mkdir(root,{recursive:true});
for(const [i,duration] of [4,6,8,10,12].entries())execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y',
  '-f','lavfi','-i',`color=c=gray:s=160x284:r=15:d=${duration}`,'-f','lavfi','-i',`sine=frequency=440:duration=${duration}`,
  '-vf',`drawbox=x=5:y=100:w=30:h=50:color=lime:t=fill:enable='gte(t,${duration-1})'`,'-c:v','libx264','-c:a','aac',`${root}/fixture-${i}.mp4`]);
const reservation=createServer();await new Promise(done=>reservation.listen(0,'127.0.0.1',done));
const port=reservation.address().port;await new Promise(done=>reservation.close(done));
const base=`http://127.0.0.1:${port}`;
const code=`
import sys,shutil,uuid,re
from pathlib import Path
from backend import main as m
root=Path(sys.argv[1])
def search(*args):
 return [{'url':f'https://www.youtube.com/shorts/VISUAL{i:05d}','title':f'Winter fails {i}'} for i in range(5)],[]
def download(item):
 i=int(item['url'][-5:]);identity=uuid.uuid4().hex;folder=m.DATA/'media'/identity;folder.mkdir()
 shutil.copyfile(root/f'fixture-{i}.mp4',folder/'source')
 return {**m.register(folder/'source',identity,item['title'],fast_preview=True),'source_url':item['url']}
def remote(payload,**kwargs):
 prompt=payload['messages'][0]['content'];evidence=payload['messages'][1]['content']
 assert any(c['type']=='image_url' for c in evidence)
 if 'SCOUT PASS' in prompt:
  if (root/'reject').exists():return {'shortlist':[]}
  found=[]
  for c in evidence:
   if c['type']!='text':continue
   match=re.search(r'Scene (\\d+)\\..*?Bounds ([\\d.]+)–([\\d.]+)s',c['text'])
   if match:
    i,a,b=match.groups();found.append({'scene':int(i),'start':float(a),'end':float(b)-.2})
  return {'shortlist':found[:8]}
 result=[]
 for c in evidence:
  if c['type']!='text':continue
  match=re.search(r'Scene (\\d+)\\..*?covers ([\\d.]+)–([\\d.]+)s',c['text'])
  if not match:continue
  i,a,b=match.groups();i=int(i);a=float(a);b=float(b)
  result.append({'scene':i,'topic_match':True,'complete':True,'confidence':.9,'score':30+i*10,
   'start':a,'end':b,'setup':{'time':a+.5,'observation':'Visible preparation'},
   'action':{'time':b-1.5,'observation':'Main action appears'},'outcome':{'time':b-.2,'observation':'Late result visible'},
   'title':f'Visual event {i}','voiceover':'Late result appears.','rank_note':f'Visible result {i}','reason':'Complete event in sampled frames.'})
 return {'moments':result}
def free_request(prompt,evidence,tokens):
 return remote({'messages':[{'content':prompt},{'content':evidence}]})
def paid_forbidden(*args,**kwargs):raise AssertionError('Paid API called in free workflow')
m.public_search=search;m.download_candidate=download;m.ai_request=paid_forbidden
m.local_vision.status=lambda **kwargs:{'ready':True,'supported':True,'model':m.local_vision.selected_model(),'message':'Local fixture ready'}
m.local_vision.request=free_request
import uvicorn
uvicorn.run(m.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
`;
const env={...process.env,RANK_DATA_DIR:root+'/data',STUDIO_PUBLIC:'0',STUDIO_PASSWORD:'',RANK_LOCAL_MODE:'1',OPENAI_API_KEY:'must-never-be-used'};
delete env.ELEVENLABS_API_KEY;
const server=spawn('.venv/bin/python',['-c',code,root,String(port)],{env,stdio:['ignore','pipe','pipe']});
let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);
let browser;
try{
  for(let i=0;i<100;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base);
  await page.getByLabel('Vizuální model',{exact:true}).selectOption('qwen2.5vl:3b');
  await page.waitForFunction(()=>document.querySelector('.toast')?.textContent?.includes('qwen2.5vl:3b'));
  assert.equal((await (await fetch(base+'/api/local-vision/status')).json()).model,'qwen2.5vl:3b');
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#local-model')?.value==='qwen2.5vl:3b');
  await page.getByLabel('Vizuální model',{exact:true}).selectOption('qwen2.5vl:7b');
  await page.waitForFunction(()=>document.querySelector('.toast')?.textContent?.includes('qwen2.5vl:7b'));
  assert.equal((await (await fetch(base+'/api/local-vision/status')).json()).model,'qwen2.5vl:7b');
  await page.locator('#search-mode').selectOption('local');
  await page.locator('#topic').fill('winter fails');
  await page.getByLabel('Po hledání vytvořit hotový náhled').uncheck();
  await page.getByLabel('Voiceover',{exact:true}).uncheck();
  await page.getByLabel('Automaticky rozmazat nápisy, emoji a malá loga').uncheck();
  await page.getByRole('button',{name:'Najít klipy',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.visual-evidence').length===5,{},{timeout:90000});
  const lengths=await page.getByLabel(/Délka klipu/).evaluateAll(inputs=>inputs.map(i=>Number(i.value)));
  assert.ok(lengths.every(n=>n>3));assert.equal(new Set(lengths.map(Math.round)).size,5);
  const first=page.locator('.visual-evidence').first();await first.locator('summary').click();
  assert.ok((await first.innerText()).includes('Late result visible'));
  await page.locator('.save-button').click();
  const initial=await page.evaluate(()=>JSON.parse(localStorage.getItem('rank-studio-project')).clips);
  assert.ok(initial.every(c=>c.selection_version==='visual-event-v2'&&c.visual_review?.provider==='local'&&c.has_audio));
  assert.equal(await page.locator('#search-mode option[value=ai]').count(),0);
  assert.equal(await page.locator('#male-voice option[value^=openai]').count(),0);
  assert.deepEqual(initial.map(c=>c.rank_note),['Visible result 0','Visible result 1','Visible result 2','Visible result 3','Visible result 4']);
  await mkdir('.runtime/screenshots',{recursive:true});
  await page.locator('.clips-section').screenshot({path:'.runtime/screenshots/visual-selection.png'});
  await page.locator('#local-vision-panel').screenshot({path:'.runtime/screenshots/local-vision-ready.png'});
  // Old projects must not accidentally keep a billable provider or paid mode.
  await page.evaluate(()=>{
    const old=JSON.parse(localStorage.getItem('rank-studio-project'));
    old.discoveryMode='ai';old.templateMethod='ai';old.voiceSettings={provider:'openai',voice:'onyx',speed:1,delivery:''};
    localStorage.setItem('rank-studio-project',JSON.stringify(old));
  });
  await page.reload();
  await page.waitForFunction(()=>document.querySelectorAll('.visual-evidence').length===5);
  assert.equal(await page.locator('#male-voice').inputValue(),'edge:free_male');
  assert.equal(await page.locator('#search-mode').inputValue(),'free');
  assert.equal(await page.locator('#template-method').inputValue(),'free');
  await page.locator('#search-mode').selectOption('local');
  const priorThumb=await page.locator('.clip-thumb img').first().getAttribute('src');
  await page.getByRole('button',{name:'AI zdarma posoudit originály',exact:true}).click();
  await page.waitForFunction(old=>document.querySelector('.clip-thumb img')?.getAttribute('src')!==old,priorThumb,{timeout:90000});
  await page.locator('.save-button').click();
  const reviewed=await page.evaluate(()=>JSON.parse(localStorage.getItem('rank-studio-project')).clips);
  assert.ok(reviewed.every((c,i)=>c.id!==initial[i].id&&c.source_asset_id===initial[i].source_asset_id));
  await writeFile(root+'/reject','1');
  await page.getByRole('button',{name:'AI zdarma posoudit originály',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Předchozí střihy zůstaly v editoru'}).waitFor({timeout:90000});
  await page.locator('.save-button').click();
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('rank-studio-project')).clips.map(c=>c.id)),reviewed.map(c=>c.id));
  await page.getByLabel('Délka klipu 5',{exact:true}).fill('5');
  assert.equal(await page.locator('.visual-evidence').count(),4);
  assert.deepEqual(errors,[]);
  console.log('Visual review browser passed: actual two-pass image extraction, variable cuts with audio, specific rank notes, visible event evidence, full-original re-review, unchanged project after rejection, and invalidation of evidence after manual trimming. Remote vision/search/download were local fixtures; model accuracy was not measured.');
}catch(error){console.error(logs);throw error;}finally{if(browser)await browser.close();server.kill('SIGTERM');}
