import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const website = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const types = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json'};
export function demoServer(port = 4174) {
  const server = createServer(async (req,res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      const root = pathname.startsWith('/source/') ? path.join(website,'../custom_components/savant_energy') : path.join(website,'demo');
      const relative = pathname.startsWith('/source/') ? pathname.slice(8) : pathname.replace(/^\/demo\//,'').replace(/^\/$/,'index.html');
      const target = path.resolve(root, relative);
      if (!target.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
      // The only integration source exposed to the local demo is its public labels.
      if (pathname.startsWith('/source/') && relative !== 'translations/en.json') { res.writeHead(404).end(); return; }
      const content=await readFile(target);
      res.writeHead(200,{'Content-Type':types[path.extname(target)] || 'application/octet-stream'}).end(content);
    } catch { res.writeHead(404).end('Not found'); }
  });
  return new Promise(resolve=>server.listen(port,'127.0.0.1',()=>resolve(server)));
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await demoServer(); console.log('Synthetic demo: http://127.0.0.1:4174/');
}
