const fixture = await fetch('/demo/fixtures.json').then(r => r.json());
const labels = await fetch('/source/translations/en.json').then(r => r.json());
const params = new URLSearchParams(location.search);
const view = params.get('view') || 'overview';
const main = document.querySelector('#content');
const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const chart = () => `<svg class="chart" viewBox="0 0 600 200" role="img" aria-label="Synthetic hourly energy usage"><path d="M30 20H590M30 95H590M30 170H590" stroke="#dfe8ec"/>${fixture.hourlyEnergy.map((n,i) => `<rect x="${35+i*23}" y="${170-n*95}" width="16" height="${n*95}" rx="3"/>`).join('')}<text x="30" y="193">00:00</text><text x="167" y="193">06:00</text><text x="306" y="193">12:00</text><text x="444" y="193">18:00</text><text x="555" y="193">23:00</text></svg>`;
const circuitRows = () => fixture.circuits.map(c => `<div class="row"><div>${c.name}<small>${c.on?'Relay on':'Relay off'} · ${c.energy} kWh today (demo)</small></div><strong>${c.power} W</strong></div>`).join('');
const toggle = (on, label) => `<button class="toggle ${on?'on':''}" role="switch" aria-checked="${on}" aria-label="${escape(label)}"></button>`;
const sceneEditor = () => `<h2>Savant Energy Scenes</h2><div class="tabs"><button data-tab="scenes">Scenes</button><button data-tab="editor" class="active">Editor</button></div><div class="editor"><div class="scene-form"><select aria-label="Select a scene">${fixture.scenes.map(s=>`<option${s==='Evening'?' selected':''}>${s}</option>`)}</select><input aria-label="Scene name" value="Evening"><button data-save>Save</button></div><div class="scene-relays">${fixture.circuits.map(c=>`<div class="row"><span>${c.name}</span>${toggle(c.on,c.name)}</div>`).join('')}</div><p class="subtle" data-feedback>Review every relay state before saving.</p></div><div class="scene-list" hidden><input aria-label="New scene name" placeholder="New scene name">${fixture.scenes.map(s=>`<div class="row"><span>${s}</span><span class="subtle">Saved scene</span></div>`).join('')}</div>`;
const scenesList = () => `<h2>Energy scenes</h2><div class="scene-list">${fixture.scenes.map(s=>`<div class="row"><span>${s}<small>Home Assistant scene button</small></span><button data-activate="${s}">Activate</button></div>`).join('')}</div>`;
if (view === 'overview') {
  document.querySelector('#page-title').textContent='Overview';
  main.innerHTML=`<div class="welcome"><h1>Energy at home</h1><span class="subtle">Example home · illustrative dashboard</span></div><div class="grid"><div><section class="panel"><h2>Power right now</h2><div class="totals"><div class="total"><small>Home</small><strong>1.15 kW</strong><em>Supported circuit readings</em></div><div class="total"><small>Solar</small><strong>2.40 kW</strong><em>Producing</em></div><div class="total"><small>Grid export</small><strong>1.25 kW</strong><em>Sending to grid</em></div></div>${chart()}<div class="status-line"><span class="chip">Grid available</span><span>Battery state of charge: 78%</span></div></section><section class="panel">${scenesList()}</section></div><div><section class="panel"><h2>Your circuits</h2>${circuitRows()}</section><section class="panel"><h2>A connected energy system</h2><p class="subtle">Circuit readings, energy counters, and relay scenes alongside the rest of your Home Assistant home.</p><span class="chip">Current mode</span></section></div></div>`;
} else if (view === 'setup') {
  const step=labels.config.step.current_setup;
  document.querySelector('#page-title').textContent='Settings / Devices & services';
  main.innerHTML=`<section class="panel form"><h1>${escape(step.title)}</h1><p>${escape(step.description)}</p>${Object.entries(step.data).map(([key,label])=>`<label for="${key}">${escape(label)}</label><input id="${key}" value="${fixture.addresses[key]}" readonly><div class="help">${escape(step.data_description[key])}</div>`).join('')}<div class="actions"><button>Submit</button></div><p class="help">Demo form only. No connection will be made.</p></section>`;
} else if (view === 'entities') {
  const c=fixture.circuits[0];
  document.querySelector('#page-title').textContent='Settings / Devices & services / Savant Energy';
  main.innerHTML=`<section class="device"><div class="device-title"><h1>Kitchen</h1><span class="subtle">Savant Energy · example relay circuit</span><br><span class="chip">Current mode · synthetic device</span></div><section class="panel"><h2>Controls</h2><div class="row"><span>Breaker</span>${toggle(true,'Kitchen breaker')}</div></section><section class="panel"><h2>Sensors</h2>${[['Power',c.power+' W'],['Current',c.current+' A'],['Voltage',c.voltage+' V'],['Energy','482.63 kWh'],['Relay status','On']].map(([name,value])=>`<div class="row"><span>${name}</span><strong>${value}</strong></div>`).join('')}</section></section>`;
} else if (view === 'energy') {
  document.querySelector('#page-title').textContent='Energy';
  main.innerHTML=`<div class="welcome"><h1>Energy usage</h1><span class="subtle">Example day · synthetic statistics</span></div><section class="panel"><h2>Electricity consumption</h2>${chart()}<p class="subtle">Hourly usage · kWh</p></section><section class="panel"><h2>Individual devices</h2>${fixture.circuits.map(c=>`<div class="row"><span>${c.name}</span><strong>${c.energy} kWh</strong></div>`).join('')}</section>`;
} else if (view === 'scenes') {
  document.querySelector('#page-title').textContent='Overview / Energy scenes';
  main.innerHTML=`<div class="welcome"><h1>Make the evening yours</h1><span class="subtle">Illustrative scene editor · synthetic devices</span></div><section class="panel">${sceneEditor()}</section><section class="panel"><h2>Saved states, deliberate control</h2><p class="subtle">Choose a scene, review its members, and save the intended relay states. Activate it from its Home Assistant scene or button.</p></section>`;
} else if (view === 'options') {
  const step=labels.options.step.init;
  document.querySelector('#page-title').textContent='Settings / Devices & services';
  main.innerHTML=`<section class="panel options-form"><h1>${step.title}</h1><p class="subtle">${step.description}</p><label>${step.data.scan_interval}</label><select aria-label="Scan Interval"><option>5</option><option>10</option><option>15</option><option>30</option></select><label>${step.data.switch_cooldown}</label><input aria-label="Breaker Cooldown" value="15" readonly><label>${step.data.pending_confirm_multiplier}</label><input aria-label="Breaker Switch Debounce Delay" value="2" readonly>${['dmx_testing_mode','disable_scene_builder','reprovision_ssh_key'].map(key=>`<div class="row"><strong>${step.data[key]}</strong>${toggle(false,step.data[key])}</div>`).join('')}<div class="actions"><button>Submit</button></div></section>`;
} else if (view === 'social') {
  document.body.classList.add('social-view');
  main.innerHTML='<div class="social"><h1>Savant Energy <span style="color:#12654f">/ HA</span></h1><p>Your circuits. Your energy.<br>In Home Assistant.</p><p style="font-size:20px;margin-top:85px">Independent community integration<br>Not affiliated with, endorsed by, or supported by Savant.</p></div>';
} else { throw new Error('Unknown demo view'); }
main.addEventListener('click',event=>{
  const button=event.target.closest('button');
  if(!button)return;
  if(button.matches('.toggle')){ const on=button.getAttribute('aria-checked')!=='true';button.classList.toggle('on',on);button.setAttribute('aria-checked',String(on)); }
  if(button.dataset.tab){ const editor=button.dataset.tab==='editor';document.querySelector('.editor').hidden=!editor;document.querySelector('.scene-list').hidden=editor;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button)); }
  if(button.hasAttribute('data-save'))document.querySelector('[data-feedback]').textContent='Demo scene saved locally for this preview.';
  if(button.dataset.activate)button.textContent='Demo activated';
});
window.demoReady=true;
