import nextra from 'nextra';
import path from 'node:path';

const withNextra = nextra({
  defaultShowCopyCode: true,
});

export default withNextra({
  reactStrictMode: true,
  outputFileTracingRoot: process.cwd(),
  i18n: {
    locales: ['ru', 'en'],
    defaultLocale: 'ru',
  },
  webpack(config) {
    config.resolve.alias = config.resolve.alias || {};
    config.resolve.alias['next-mdx-import-source-file'] = path.join(process.cwd(), 'lib', 'next-mdx-import-source-file.js');
    return config;
  },
});
