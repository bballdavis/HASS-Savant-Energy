// Validate the actual production routes, fragments, images and source Markdown links.
import {readFile, readdir, stat} from 'node:fs/promises';
import path from 'node:path';
const base = '/HASS-Savant-Energy/';
const root = path.resolve('..');
const build = path.resolve('build');
const failures = [];
async function files(directory) {
  const entries = await readdir(directory,{withFileTypes:true});
  const result = await Promise.all(entries.map(entry=>entry.isDirectory()?files(path.join(directory,entry.name)):[path.join(directory,entry.name)]));
  return result.flat();
}
async function exists(filename) { try { return (await stat(filename)).isFile(); } catch { return false; } }
const html = new Map(await Promise.all((await files(build)).filter(p=>p.endsWith('.html')).map(async p=>[p,await readFile(p,'utf8')])));
let count = 0;
for (const [filename,content] of html) {
  const relative = path.relative(build, filename).split(path.sep).join('/').replace(/index\.html$/,'');
  const origin = new URL(base+relative,'https://docs.invalid');
  for (const match of content.matchAll(/\b(?:href|src)=["']([^"']+)["']/g)) {
    const raw = match[1].replace(/&amp;/g,'&');
    if (/^(?:https?:|mailto:|data:|tel:|javascript:|\/\/)/.test(raw)) continue;
    const target = new URL(raw,origin);
    if (!target.pathname.startsWith(base)) { failures.push(`${relative}: path escapes project base: ${raw}`);continue; }
    const local = decodeURIComponent(target.pathname.slice(base.length));
    let dest=path.join(build,local);
    if (!(await exists(dest))) dest=path.join(dest,'index.html');
    if (!(await exists(dest))) { failures.push(`${relative}: missing ${raw}`);continue; }
    count++;
    if (target.hash && html.has(dest)) {
      const id=decodeURIComponent(target.hash.slice(1));
      const escaped=id.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      if (!(new RegExp(`\\b(?:id|name)=["']${escaped}["']`)).test(html.get(dest))) failures.push(`${relative}: missing fragment ${raw}`);
    }
  }
}
for (const filename of [path.join(root,'README.md'),path.join(root,'INTEGRATION_API.md'),...(await files(path.join(root,'docs'))).filter(p=>p.endsWith('.md'))]) {
  const source=(await readFile(filename,'utf8')).replace(/```[\s\S]*?```/g,'');
  for (const match of source.matchAll(/!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
    const href=match[1];if (/^(?:https?:|mailto:|#)/.test(href))continue;
    const dest=path.resolve(path.dirname(filename),decodeURIComponent(href.split('#')[0]));
    if (!(await exists(dest)))failures.push(`${path.relative(root,filename)}: missing Markdown target ${href}`);
  }
}
if(failures.length) {console.error(failures.join('\n'));process.exit(1);}
console.log(`Checked ${html.size} HTML pages and ${count} local links/assets; source Markdown targets exist.`);
