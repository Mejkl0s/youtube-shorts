'use strict';
// Private sidecar requests never use ambient HTTP_PROXY or a system proxy.
const http=require('node:http');
const {Readable}=require('node:stream');
const {pipeline}=require('node:stream/promises');
const agent=new http.Agent({keepAlive:true,maxSockets:10,proxyEnv:{}});
async function localFetch(value,options={}){
  const url=new URL(value);
  if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||url.username||url.password)throw Error('Nepovolená adresa místního backendu.');
  const prepared=new Request(url,{method:options.method||'GET',headers:options.headers,body:options.body});
  return new Promise((resolve,reject)=>{
    const request=http.request(url,{method:prepared.method,headers:Object.fromEntries(prepared.headers),agent,signal:options.signal},response=>{
      const headers=new Headers();for(const [name,value] of Object.entries(response.headers))if(value!==undefined)headers.set(name,Array.isArray(value)?value.join(', '):value);
      const noBody=[204,205,304].includes(response.statusCode);
      if(noBody)response.resume();
      resolve(new Response(noBody?null:Readable.toWeb(response),{status:response.statusCode,headers}));
    });
    request.once('error',reject);
    if(prepared.body)pipeline(Readable.fromWeb(prepared.body),request).catch(error=>{request.destroy();reject(error);});
    else request.end();
  });
}
module.exports={localFetch};
