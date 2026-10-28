// Loopback-only UI, speech service and proxy to the local FastAPI lesson worker.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { createHash } = require('node:crypto');
const allowed = new Map([
  ['/public/blu/poses.png', ['public/blu/poses.png', 'image/png']],
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ...['chat.css', 'companion-preview.css'].map(name => ['/src/' + name, ['src/' + name, 'text/css; charset=utf-8']]),
  ...['chat.js', 'companion-preview.js'].map(name => ['/src/' + name, ['src/' + name, 'text/javascript; charset=utf-8']]),
  ...['blu-3d.js', 'blu-voice.js','motion-math.mjs'].map(name => ['/src/' + name, ['src/' + name, 'text/javascript; charset=utf-8']]),
  ['/src/blu-stage.css', ['src/blu-stage.css', 'text/css; charset=utf-8']],
  ...['three.module.js','three.core.js'].map(name => ['/vendor/' + name, ['node_modules/three/build/' + name, 'text/javascript; charset=utf-8']]),
  ['/vendor/THREE-LICENSE.txt', ['node_modules/three/LICENSE', 'text/plain; charset=utf-8']],
  ['/public/blu-reference.png', ['public/blu-reference.png', 'image/png']],
]);
function json(response,status,value){response.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});response.end(JSON.stringify(value));}
const server = http.createServer(async (request, response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (pathname.startsWith('/api/lessons') || pathname==='/api/health' || pathname==='/api/voices' || pathname==='/api/speech' || pathname==='/api/transcribe' || pathname.startsWith('/audio/')) {
    if(request.headers.origin && request.headers.origin!=='http://127.0.0.1:53841'){json(response,403,{error:'Local studio origin required.'});return;}
    const upstream=http.request({hostname:'127.0.0.1',port:53842,path:request.url,method:request.method,headers:{...(request.headers['content-type']?{'content-type':request.headers['content-type']}:{}),...(request.headers.range?{range:request.headers.range}:{})}},res=>{response.writeHead(res.statusCode,res.headers);res.pipe(response)});
    upstream.on('error',()=>{if(!response.headersSent)json(response,503,{detail:'The local lesson engine is not running. Start npm run studio.'});else response.end()});
    request.pipe(upstream);return;
  }
  const entry = allowed.get(new URL(request.url, 'http://localhost').pathname);
  if (!entry) { response.writeHead(404); response.end('Not found'); return; }
  fs.readFile(path.join(__dirname, entry[0]), (error, data) => {
    if (error) { response.writeHead(500); response.end('Preview asset unavailable'); return; }
    response.writeHead(200, { 'Content-Type': entry[1], 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    response.end(data);
  });
});
server.on('error', error => { console.error(error.message); process.exit(1); });
server.listen(53841, '127.0.0.1', () => console.log('Biryani preview: http://127.0.0.1:53841'));
