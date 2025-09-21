import type { GetServerSideProps } from 'next';
import fs from 'node:fs';
import path from 'node:path';

type Item = {
  slug: string;
  path: string;
  title: string;
  date?: string | null;
  tags: string[];
  language?: string;
  status: 'public' | 'private';
};

type Props = {
  items: Item[];
};

export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const file = path.join(process.cwd(), '.data', 'index-all.json');
  const raw = fs.readFileSync(file, 'utf-8');
  const items: Item[] = JSON.parse(raw);
  return { props: { items } };
};

export default function All({ items }: Props) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-bold mb-4">Все статьи (public + private)</h1>
      <ul className="list-disc ml-5">
        {items.map((i) => (
          <li key={i.slug}>
            <a href={i.path}>{i.title}</a>
            {i.date ? <span className="opacity-70"> — {i.date}</span> : null}
            {i.language ? <span className="opacity-70"> — {i.language.toUpperCase()}</span> : null}
            <span
              className="ml-2 text-xs px-2 py-0.5 rounded"
              style={{ background: i.status === 'private' ? '#fde68a' : '#bbf7d0' }}
            >
              {i.status}
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}
