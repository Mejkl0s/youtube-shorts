// Exercises real password login without browser HTTP credentials or provider mocks.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:net';

const listener=createServer();
await new Promise(resolve=>listener.listen(0,'127.0.0.1',resolve));
const port=listener.address().port;
await new Promise(resolve=>listener.close(resolve));
const base=`http://127.0.0.1:${port}`;
const password=randomBytes(24).toString('hex');
const data=await mkdtemp(join(tmpdir(),'rank-login-'));
const server=spawn('.venv/bin/python',['-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',String(port),'--no-access-log'],{env:{...process.env,STUDIO_PUBLIC:'0',STUDIO_USERNAME:'owner',STUDIO_PASSWORD:password,RANK_DATA_DIR:data},stdio:'ignore'});
let browser,page;
const consoleErrors=[];
try {
  let ready=false;
  for(let i=0;i<100;i++){
    if(server.exitCode!==null)throw new Error('Login test server exited before startup.');
    try{ready=(await fetch(base+'/api/health')).ok;}catch{}
    if(ready)break;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.ok(ready,'Login test server did not become ready.');
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  page=await browser.newPage({viewport:{width:390,height:844}});
  page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const response=await page.goto(base);
  assert.equal(response.status(),200);
  assert.ok(!response.headers()['www-authenticate']);
  await page.getByRole('heading',{name:'Přihlas se do svého studia'}).waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await mkdir('.runtime/screenshots',{recursive:true});
  await page.screenshot({path:'.runtime/screenshots/login-mobile.png',fullPage:true});
  await page.getByLabel('Heslo',{exact:true}).fill('wrong');
  await page.getByRole('button',{name:'Otevřít ranking studio'}).click();
  await page.getByRole('alert').filter({hasText:'Nesprávné jméno nebo heslo'}).waitFor();
  assert.equal((await page.request.get(base+'/api/fonts/bold')).status(),401);
  await page.getByLabel('Heslo',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Otevřít ranking studio'}).click();
  await page.getByRole('heading',{name:/Tvoje ranking klipy/}).waitFor();
  assert.equal(await page.locator('.clip-card').count(),5);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const cookies=await page.context().cookies();
  const session=cookies.find(cookie=>cookie.name==='rank_studio_session');
  assert.ok(session?.httpOnly);
  assert.equal(session.sameSite,'Lax');
  assert.equal((await page.request.get(base+'/api/fonts/bold')).status(),200);
  await page.reload();
  await page.getByRole('heading',{name:/Tvoje ranking klipy/}).waitFor();
  // Real browser-origin POSTs and an actual FFmpeg export stay usable after login.
  const demo=await page.evaluate(async()=>{const r=await fetch('/api/demo',{method:'POST'});if(!r.ok)throw Error('Protected demo failed: '+r.status);return r.json();});
  assert.equal(demo.clips.length,5);
  const job=await page.evaluate(async payload=>{const r=await fetch('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok)throw Error('Protected render failed: '+r.status);return r.json();},{title:'LOGIN TEST TOP FIVE',voice:false,effects:true,resolution:'720',clips:demo.clips.map(clip=>({...clip,start:0,duration:2}))});
  let completed;
  for(let i=0;i<240;i++){
    completed=await (await page.request.get(base+'/api/jobs/'+job.id)).json();
    if(completed.status==='failed')throw Error(completed.message);
    if(completed.status==='done')break;
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  assert.equal(completed.status,'done');
  const video=await page.request.get(base+completed.download);
  assert.equal(video.status(),200);
  assert.match(video.headers()['content-type'],/video\/mp4/);
  assert.ok((await video.body()).length>10000);
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Odhlásit se',exact:true}).click();
  await page.getByRole('heading',{name:'Přihlas se do svého studia'}).waitFor();
  assert.ok(!(await page.context().cookies()).some(cookie=>cookie.name==='rank_studio_session'));
  assert.equal((await page.request.get(base+'/api/fonts/bold')).status(),401);
  assert.equal((await page.request.get(base+completed.download)).status(),401);
  await page.screenshot({path:'.runtime/screenshots/login-desktop.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Browser login passed: HTML login, wrong-password rejection, five-clip editor, protected assets, refresh, HttpOnly cookie, real FFmpeg MP4 export/download, logout and mobile layout; no native auth popup or provider mocks.');
} catch(error) {
  if(page){console.error('Login page diagnostic:',JSON.stringify({url:page.url(),text:(await page.locator('body').innerText()).slice(0,800),consoleErrors}));await page.screenshot({path:'.runtime/screenshots/login-failure.png',fullPage:true});}
  throw error;
} finally {
  if(browser)await browser.close();
  server.kill('SIGTERM');
  if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve));
  await rm(data,{recursive:true,force:true});
}
