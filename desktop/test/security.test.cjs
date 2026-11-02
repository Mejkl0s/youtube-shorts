const {test}=require('node:test');
const assert=require('node:assert/strict');
const {trustedSender,stateInput,externalURL,preferences}=require('../security.cjs');
test('IPC accepts only the application main frame on the exact session origin',()=>{
  const main={url:'http://127.0.0.1:54321/'};const event={senderFrame:main,sender:{mainFrame:main}};
  assert.equal(trustedSender(event,'http://127.0.0.1:54321'),true);
  assert.equal(trustedSender(event,'http://127.0.0.1:54322'),false);
  assert.equal(trustedSender({...event,senderFrame:{url:main.url}},'http://127.0.0.1:54321'),false);
  assert.equal(trustedSender({senderFrame:{url:'file:///etc/passwd'}},'http://127.0.0.1:54321'),false);
});
test('renderer state cannot persist credentials or arbitrary settings',()=>{
  assert.deepEqual(stateInput({'rank-studio-project':'{}'}),{'rank-studio-project':'{}'});
  for(const value of [{apiKey:'secret'},{'rank-studio-project':{malformed:true}},{'rank-studio-chat':'invalid'}])assert.throws(()=>stateInput(value));
});
test('external links are HTTPS and restricted to known documentation and video sources',()=>{
  assert.equal(externalURL('https://ollama.com/download/windows'),'https://ollama.com/download/windows');
  for(const url of ['file:///etc/passwd','javascript:alert(1)','https://ollama.com.evil.invalid','https://user:pass@ollama.com','https://127.0.0.1'])assert.throws(()=>externalURL(url));
});
test('preference input cannot expand the native capability surface',()=>{
  assert.deepEqual(preferences({closeBehavior:'execute',startAtLogin:'yes',command:'powershell'}),{closeBehavior:'quit',minimizeToTray:false,startAtLogin:false,language:'cs',autoCheckUpdates:false});
});
