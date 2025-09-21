'use client';

import { useEffect, useState } from 'react';

type BacklinksMap = Record<string, string[]>;
type SlugInfoEntry = { path: string; title: string; language?: string; canonical?: string };
type SlugInfo = Record<string, SlugInfoEntry>;

export function Backlinks({ slug, scope }: { slug: string; scope: 'public' | 'all' }) {
  const [backlinks, setBacklinks] = useState<string[]>([]);
  const [slugsInfo, setSlugsInfo] = useState<SlugInfo>({});

  useEffect(() => {
    async function load() {
      if (scope === 'public') {
        const [bl, s] = await Promise.all([
          fetch('/backlinks-public.json').then((r) => r.json()),
          fetch('/slugs-public.json').then((r) => r.json()),
        ]);
        setBacklinks((bl as BacklinksMap)[slug] || []);
        setSlugsInfo(s as SlugInfo);
      } else {
        // приватные данные — через защищённый API
        const [bl, s] = await Promise.all([
          fetch(`/api/private/backlinks?slug=${encodeURIComponent(slug)}`).then((r) => r.json()),
          fetch('/api/private/slugs').then((r) => r.json()),
        ]);
        setBacklinks(bl as string[]);
        setSlugsInfo(s as SlugInfo);
      }
    }
    load().catch(() => {});
  }, [slug, scope]);

  if (!backlinks.length) return null;

  return (
    <section style={{ marginTop: '3rem' }}>
      <h3>Обратные ссылки</h3>
      <ul>
        {backlinks.map((b) => {
          const info = slugsInfo[b];
          const href = info?.path ?? `/n/${b}`;
          const title = info?.title ?? b;
          const label = info?.language ? `${title} (${info.language.toUpperCase()})` : title;
          return (
            <li key={b}>
              <a href={href}>{label}</a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
