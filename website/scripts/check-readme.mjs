// Verify the README's image/link syntax against HACS's relative URL handling.
// Source: https://github.com/hacs/frontend/blob/main/src/tools/markdown.ts
// This is a compatibility check, not an installed HACS session.
import assert from 'node:assert/strict';
import {readFile,access} from 'node:fs/promises';
import path from 'node:path';
const text=await readFile('../README.md','utf8');
assert(!/<img[^>]+src=["'](?!https?:)/i.test(text),'HACS does not rewrite relative HTML image URLs; use Markdown images');
const transformed=text.replace(/\[.*?\]\([^#](?!.*?:\/\/).*?\)/g,match=>{
  const web=/\.md|\.markdown/i.test(match);
  return match.replace('(/','(').replace('(',`(https://${web?'github.com':'raw.githubusercontent.com'}/bballdavis/HASS-Savant-Energy${web?'/blob':''}/main/`);
});
let images=0;
for(const match of text.matchAll(/!?\[[^\]]*\]\(([^)\s]+)\)/g)){
  const href=match[1];
  if(/^(?:https?:|#)/.test(href))continue;
  await access(path.resolve('..',href));
  assert(transformed.includes(`/main/${href}`),`HACS link did not resolve: ${href}`);
  if(match[0].startsWith('!'))images++;
}
assert.equal(images,2,'README should have an original wordmark and one showcase image');
assert(text.includes('This is an independent community project and is not affiliated with, endorsed by, or supported by Savant.'));
assert(text.split('\n').length<110,'Keep the README compact');
console.log('README: local targets exist; wordmark and dashboard use HACS-compatible Markdown; non-affiliation statement present.');
