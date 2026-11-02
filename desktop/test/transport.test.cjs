const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {localFetch}=require('../transport.cjs');
test('private transport streams multipart, preserves headers and refuses redirects',async()=>{
  let calls=0;
  const server=createServer(async(request,response)=>{calls++;let body='';for await(const chunk of request)body+=chunk;
    assert.equal(request.headers['x-rank-desktop-token'],'fixture-token');
    if(request.url==='/redirect'){response.writeHead(302,{Location:'https://outside.invalid'});return response.end();}
    response.setHeader('content-type','application/json');response.end(JSON.stringify({body,type:request.headers['content-type']}));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url=`http://127.0.0.1:${server.address().port}`;
  try{
    const form=new FormData();form.append('file',new Blob(['fixture-media']),'clip.rankstudio');
    const response=await localFetch(url+'/import',{method:'POST',headers:{'X-Rank-Desktop-Token':'fixture-token'},body:form});
    const data=await response.json();assert.ok(data.body.includes('fixture-media'));assert.ok(data.type.startsWith('multipart/form-data; boundary='));
    assert.equal((await localFetch(url+'/redirect',{headers:{'X-Rank-Desktop-Token':'fixture-token'}})).status,302);assert.equal(calls,2);
    await assert.rejects(localFetch('https://outside.invalid'));
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
