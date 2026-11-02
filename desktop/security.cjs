'use strict';
const {URL}=require('node:url');
const STATE_KEYS=new Set(['rank-studio-project','rank-studio-chat','rank-studio-assets','rank-studio-sources','rank-studio-previous-clips','rank-studio-writing']);
function trustedSender(event,origin){
  try{return !!origin&&event.senderFrame?.url&&new URL(event.senderFrame.url).origin===origin&&event.senderFrame===event.sender.mainFrame;}
  catch{return false;}
}
function stateInput(value){
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!STATE_KEYS.has(k)))throw Error('Neplatný stav projektu.');
  if(Buffer.byteLength(JSON.stringify(value))>8*1024*1024)throw Error('Projekt je příliš velký.');
  for(const text of Object.values(value)){if(typeof text!=='string')throw Error('Neplatný stav projektu.');JSON.parse(text);}
  return value;
}
function externalURL(value){
  const url=new URL(value);
  const domains=['ollama.com','lmstudio.ai','github.com','huggingface.co','openai.com','anthropic.com','google.dev','deepseek.com','openrouter.ai','youtube.com','youtu.be','tiktok.com','instagram.com'];
  if(url.protocol!=='https:'||url.username||url.password||!domains.some(d=>url.hostname===d||url.hostname.endsWith('.'+d)))throw Error('Odkaz není v seznamu podporovaných zdrojů.');
  return url.href;
}
function preferences(value){
  if(!value||typeof value!=='object')throw Error('Neplatné nastavení.');
  return {closeBehavior:value.closeBehavior==='tray'?'tray':'quit',minimizeToTray:value.minimizeToTray===true,
    startAtLogin:value.startAtLogin===true,language:value.language==='en'?'en':'cs',autoCheckUpdates:value.autoCheckUpdates===true};
}
module.exports={trustedSender,stateInput,externalURL,preferences};
