import {chromium} from 'playwright';
import {mkdir, writeFile} from 'node:fs/promises';
import {demoServer} from './serve-demo.mjs';
const server = await demoServer(0);
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch();
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1,colorScheme:'light'});
  // Demo capture must never contact a service, public CDN, or hardware.
  await page.route('**/*',route=>route.request().url().startsWith(origin + '/') ? route.continue() : route.abort());
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await mkdir('../docs/assets',{recursive:true});
  for (const view of ['overview','setup','entities','energy','scenes','options','social']) {
    await page.setViewportSize(view==='social'?{width:1200,height:630}:{width:1440,height:1000});
    await page.goto(`${origin}/?view=${view}`);
    await page.waitForFunction(()=>window.demoReady===true);
    await page.evaluate(()=>document.fonts.ready);
    const filename=view==='social'?'static/img/social-card.png':`../docs/assets/${view}.png`;
    await page.screenshot({path:filename,fullPage:true});
    console.log('Captured ' + view);
  }
  if(errors.length)throw new Error(errors.join('\n'));
  await writeFile('../docs/assets/provenance.json',JSON.stringify({origin:'Original browser-rendered illustrative UI; no vendor artwork, live data, or AI-generated UI text',source:'website/demo/',fixtures:'website/demo/fixtures.json',command:'cd website && npm run demo:capture',images:['overview.png','setup.png','entities.png','energy.png','scenes.png','options.png'],labels:'custom_components/savant_energy/translations/en.json',disclaimer:'Synthetic documentation examples; not proof of live integration behavior'},null,2)+'\n');
} finally { await browser.close();await new Promise(resolve=>server.close(resolve)); }
