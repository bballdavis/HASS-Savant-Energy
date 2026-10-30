import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';
const sidebars: SidebarsConfig = {
  guides: [
    {type: 'category', label: 'Get started', collapsed: false, items: ['get-started/overview', 'get-started/requirements', 'get-started/installation']},
    {type: 'category', label: 'Connect your system', collapsed: false, items: ['connect/current', 'connect/verify']},
    {type: 'category', label: 'Use the integration', items: ['usage/companion-card', 'usage/entities', 'usage/energy-dashboard', 'usage/controls', 'usage/scenes', 'usage/options']},
    {type: 'category', label: 'Legacy and migration', items: ['legacy/README', 'legacy/migration']},
    {type: 'category', label: 'Troubleshooting', items: ['troubleshooting/overview', 'troubleshooting-ssh', 'troubleshooting/telemetry', 'troubleshooting/scenes-card', 'troubleshooting/logs']},
    {type: 'category', label: 'Reference', items: ['reference/generated/services', 'reference/generated/options', 'reference/generated/setup', 'reference/generated/errors', 'reference/rest-api', 'current-api-workflow']},
    {type: 'category', label: 'Development', items: ['development/contributing', 'development/documentation', 'live-diagnostics', 'development/releases', 'release-notes-v2.0.0', 'release-notes-v2.0.1-beta7', 'release-notes-v2.0.1-beta8', 'release-notes-v2.0.1-beta9']},
  ],
};
export default sidebars;
