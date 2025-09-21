import type { GetServerSideProps } from 'next';
import fs from 'node:fs';
import path from 'node:path';

type Slugs = Record<string, { path: string }>;

export const getServerSideProps: GetServerSideProps = async ({ params }) => {
  const slug = String(params?.slug || '');
  const file = path.join(process.cwd(), '.data', 'slugs-all.json');

  if (!fs.existsSync(file)) {
    return { redirect: { destination: '/', permanent: false } };
  }

  const data: Slugs = JSON.parse(fs.readFileSync(file, 'utf-8'));
  const info = data[slug];
  const dest = info?.path || '/';

  return { redirect: { destination: dest, permanent: false } };
};

export default function NSlug() {
  return null;
}
