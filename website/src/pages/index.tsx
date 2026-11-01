import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import overview from '@site/../docs/assets/breaker-board-desktop.jpg';

export default function Home(): React.JSX.Element {
  return <Layout title="Your system. Your data." description="Independent community integration for Savant energy systems. Installation, setup, energy monitoring, scenes, and Legacy guides.">
    <main>
      <section className="showcase container">
        <div className="showcase-copy">
          <h1>Your system. Your data.<br /><span>In Home Assistant.</span></h1>
          <p>Bring your Savant energy system into the home you already manage. See supported circuit readings, monitor energy, and run relay scenes from Home Assistant.</p>
          <div className="showcase-actions">
            <Link className="button button--primary button--lg" to="/docs/get-started/installation">Install the integration</Link>
            <Link className="text-link" to="/docs/usage/companion-card">Explore the companion card <span aria-hidden="true">→</span></Link>
          </div>
          <p className="community-note">Independent community project. Not affiliated with Savant.</p>
        </div>
        <figure className="showcase-image">
          <img src={overview} width="1608" height="602" alt="The companion breaker-board card running in Home Assistant with real circuit tiles, wattage, and history graphs." fetchPriority="high" />
          <figcaption>Real Home Assistant capture · companion breaker-board card</figcaption>
        </figure>
      </section>
      <section className="capabilities container" aria-labelledby="capabilities-title">
        <h2 id="capabilities-title">One integration. A clearer view of your home.</h2>
        <div className="capability-list">
          <article><h3>See what each circuit uses</h3><p>Power and hardware energy counters for supported loads, plus current, voltage, and system readings where your firmware provides them.</p><Link to="/docs/usage/entities">Explore devices and entities →</Link></article>
          <article><h3>Bring energy into focus</h3><p>Add eligible cumulative energy sensors to Home Assistant’s Energy dashboard. Understand which readings are available on your system.</p><Link to="/docs/usage/energy-dashboard">Set up energy monitoring →</Link></article>
          <article><h3>Make controls part of your day</h3><p>Use the included companion breaker board for circuit tiles and compact mobile views. Review saved relay states in its scene editor.</p><Link to="/docs/usage/scenes">Build your first scene →</Link></article>
        </div>
      </section>
      <section className="setup-path container" aria-labelledby="setup-title">
        <div><h2 id="setup-title">A setup path for your system.</h2><p>Start with installation, connect your controller, then verify the first readings. Older firmware has its own complete guide.</p></div>
        <div className="path-links">
          <Link to="/docs/connect/current"><strong>Auto & Current setup</strong><span>New installations and firmware 11.2 or later →</span></Link>
          <Link to="/docs/legacy/"><strong>Legacy setup</strong><span>Original snapshot and DMX workflow →</span></Link>
          <Link to="/docs/legacy/migration"><strong>Moving from Legacy?</strong><span>Reconfigure an existing installation →</span></Link>
        </div>
      </section>
    </main>
  </Layout>;
}
