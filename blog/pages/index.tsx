import { useEffect, useState } from 'react';

type Item = {
  slug: string;
  path: string;
  title: string;
  date?: string | null;
  tags: string[];
  category?: string | null;
  language?: string;
};

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    fetch('/index-public.json')
      .then((r) => r.json())
      .then((data) => setItems(data as Item[]))
      .catch(() => setItems([]));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-bold mb-4">Публичные статьи</h1>
      <ul className="list-disc ml-5">
        {items.map((i) => (
          <li key={i.slug}>
            <a href={i.path}>{i.title}</a>
            {i.date ? <span className="opacity-70"> — {i.date}</span> : null}
            {i.tags?.length ? <span className="opacity-70"> — {i.tags.join(', ')}</span> : null}
            {i.language ? <span className="opacity-70"> — {i.language.toUpperCase()}</span> : null}
          </li>
        ))}
      </ul>
      <p className="mt-6">
        Полный индекс (доступ только с правами): <a href="/all">/all</a>
      </p>
    </main>
  );
}
