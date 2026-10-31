// Exercise the actual shipped JavaScript in jsdom, using the pinned upstream test dependency.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=process.argv[2];
if(!source)throw new Error('Usage: node tools/test_companion.mjs <upstream Savant-Card checkout with npm ci>');
const require=createRequire(path.resolve(source,'package.json'));
const {JSDOM}=require('jsdom');
const bundle=readFileSync(path.join(root,'custom_components/savant_energy/www/Savant-Card.js'),'utf8');
const alias=readFileSync(path.join(root,'custom_components/savant_energy/www/savant-energy-scenes-card.js'),'utf8');
function dom(){
 const d=new JSDOM('<!doctype html><body></body>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
 d.window.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};
 d.window.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
 return d;
}
// Fresh install, duplicate bundle/resource URLs, old YAML alias, picker and editor.
{
 const d=dom(); const w=d.window;
 w.eval(bundle); w.eval(bundle); w.eval(alias); w.eval(alias);
 await Promise.resolve();
 assert(w.customElements.get('savant-energy-breaker-board-card'));
 assert(w.customElements.get('savant-energy-breaker-board-card-editor'));
 assert.equal(w.customCards.filter(c=>c.type==='savant-energy-breaker-board-card').length,1);
 const legacy=w.document.createElement('savant-energy-scenes-card');
 legacy.setConfig({type:'custom:savant-energy-scenes-card',show_header:false});
 assert.equal(legacy.config.type,'custom:savant-energy-breaker-board-card');
 assert.equal(legacy.config.display.show_title,false);
 assert.equal(legacy.constructor.getConfigElement().localName,'savant-energy-breaker-board-card-editor');
 // Rendering a fresh card must not call switch services or write scene state.
 let writes=0;
 const board=w.document.createElement('savant-energy-breaker-board-card');
 board.setConfig({type:'custom:savant-energy-breaker-board-card'});
 board.hass={states:{},callService:async()=>{writes++},callApi:async(method)=>{if(method!=='GET')writes++;return {scenes:[]}},
  connection:{sendMessagePromise:async()=>[]}};
 w.document.body.append(board);
 await board.updateComplete;
 await new Promise(resolve=>setTimeout(resolve,20));
 assert.equal(writes,0);
 assert(board.shadowRoot.querySelector('ha-card'));
 d.window.close();
}
// Existing HACS copy loads first: bundled copy must not redefine its elements.
{
 const d=dom();d.window.eval(readFileSync(path.resolve(source,'dist/Savant-Card.js'),'utf8'));
 const existing=d.window.customElements.get('savant-energy-breaker-board-card');
 d.window.eval(bundle);d.window.eval(alias);await Promise.resolve();
 assert.equal(d.window.customElements.get('savant-energy-breaker-board-card'),existing);
 assert(d.window.customElements.get('savant-energy-scenes-card'));
 d.window.close();
}
// Legacy compatibility resource can arrive before the asynchronously loaded board.
{
 const d=dom();d.window.eval(alias);d.window.eval(bundle);await Promise.resolve();
 assert(d.window.customElements.get('savant-energy-scenes-card'));
 d.window.close();
}
console.log('Shipped companion: registration, duplicate loads, HACS coexistence, legacy YAML/editor, render without writes passed.');
