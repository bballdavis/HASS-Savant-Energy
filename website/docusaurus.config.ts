import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Savant Energy for Home Assistant',
  tagline: 'Your circuits. Your energy. In Home Assistant.',
  favicon: 'img/favicon.svg',
  url: 'https://bballdavis.github.io',
  baseUrl: '/HASS-Savant-Energy/',
  organizationName: 'bballdavis',
  projectName: 'HASS-Savant-Energy',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  markdown: {hooks: {onBrokenMarkdownLinks: 'throw', onBrokenMarkdownImages: 'throw'}},
  i18n: {defaultLocale: 'en', locales: ['en']},
  presets: [['classic', {
    docs: {
      path: '../docs', routeBasePath: 'docs', sidebarPath: './sidebars.ts',
      exclude: ['assets/**'],
      editUrl: ({docPath}: {docPath: string}) => `https://github.com/bballdavis/HASS-Savant-Energy/edit/main/docs/${docPath}`,
      showLastUpdateTime: false,
    },
    blog: false,
    theme: {customCss: './src/css/custom.css'},
  } satisfies Preset.Options]],
  themes: [['@easyops-cn/docusaurus-search-local', {
    hashed: 'filename', language: ['en'], indexPages: true, indexBlog: false,
    docsDir: '../docs', docsRouteBasePath: '/docs',
  }]],
  plugins: [['@docusaurus/plugin-client-redirects', {
    redirects: [
      {from: '/docs/legacy/README', to: '/docs/legacy/'},
      {from: '/docs/installation', to: '/docs/get-started/installation/'},
      {from: '/docs/setup', to: '/docs/connect/current/'},
      {from: '/docs/INTEGRATION_API', to: '/docs/reference/rest-api/'},
    ],
  }]],
  themeConfig: {
    image: 'img/social-card.png',
    colorMode: {defaultMode: 'light', respectPrefersColorScheme: true},
    navbar: {
      title: 'Savant Energy',
      items: [
        {to: '/docs/get-started/installation', label: 'Get started', position: 'left'},
        {type: 'docSidebar', sidebarId: 'guides', label: 'Guides', position: 'left'},
        {to: '/docs/legacy/', label: 'Legacy', position: 'left'},
        {to: '/docs/reference/generated/services', label: 'Reference', position: 'left'},
        {href: 'https://github.com/bballdavis/HASS-Savant-Energy', label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'light',
      links: [
        {title: 'Start here', items: [{label: 'Installation', to: '/docs/get-started/installation'}, {label: 'Connect your system', to: '/docs/connect/current'}]},
        {title: 'Get help', items: [{label: 'Troubleshooting', to: '/docs/troubleshooting/overview'}, {label: 'Report an issue', href: 'https://github.com/bballdavis/HASS-Savant-Energy/issues'}]},
        {title: 'Project', items: [{label: 'Source & license', href: 'https://github.com/bballdavis/HASS-Savant-Energy'}, {label: 'Release history', to: '/docs/development/releases'}]},
      ],
      copyright: 'Independent community software · GPL-3.0<br />This is an independent community project and is not affiliated with, endorsed by, or supported by Savant.',
    },
    prism: {additionalLanguages: ['bash', 'json', 'yaml', 'python', 'powershell']},
  } satisfies Preset.ThemeConfig,
};
export default config;
