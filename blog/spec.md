PRD (обновлённый)
Цель

Git-first: контент в content/blog/*.md|mdx.

Zettelkasten-смысл: атомарные заметки, [[wikilink]], обратные ссылки.

Разделение доступа:

Публично: только статьи со status: public, публичный индекс, публичные бэклинки (показывают связи только между public-заметками).

Приватно (Zero Trust): полный индекс, все статьи, все бэклинки, резолвер /n/[slug].

Никаких приватных индексов/карт/слуг-мапов в /public.

Факты хранения

Frontmatter (в каждой заметке):

title: string
description?: string
date?: YYYY-MM-DD
tags?: string[]
category?: string
status: public | private   # по умолчанию private


Генерация (скрипт scripts/sync-content.mjs):

Генерит MDX-страницы:

public → pages/blog/<slug>.mdx

private → pages/private/<slug>.mdx (добавляем <meta name="robots" content="noindex,nofollow">)

Заменяет [[slug]] → ссылки на /n/<slug>.

Считает двунаправленные ссылки.

Пишет JSON:

публичные → public/index-public.json, public/backlinks-public.json, public/slugs-public.json

приватные → .data/index-all.json, .data/backlinks-all.json, .data/slugs-all.json (в корне проекта, вне веб-папки)

Роутинг / доступ

/ — публичный индекс (читает index-public.json)

/blog/[post] — публичная статья

/all — закрыть Cloudflare Zero Trust, SSR читает /.data/index-all.json

/private/[post] — закрыть Cloudflare Zero Trust

/n/[slug] — закрыть Cloudflare Zero Trust, SSR читает /.data/slugs-all.json и редиректит к правильному пути (public/private)

/api/private/* — закрыть Cloudflare Zero Trust:

/api/private/backlinks?slug=... → из /.data/backlinks-all.json

/api/private/slugs → из /.data/slugs-all.json

(при желании /api/private/index → из /.data/index-all.json)

Публичность/утечки

На публичных страницах бэклинки берём только из backlinks-public.json, чтобы не засветить названия/существование приватных заметок.

/n/*, /all, /private/*, /api/private/* прикрываем Zero Trust → без доступа не узнать даже факт существования приватного слага.

Код (готовый скелет)
0) Твой package.json — уже ок (см. предыдущий пост).
1) next.config.mjs
import withNextra from 'nextra' assert { type: 'function' };

export default withNextra({
  theme: 'nextra-theme-blog',
  themeConfig: './theme.config.tsx',
  defaultShowCopyCode: true
})({
  reactStrictMode: true
});

2) theme.config.tsx
import type { BlogThemeConfig } from 'nextra-theme-blog';

const config: BlogThemeConfig = {
  name: 'reports-blog',
  footer: <small>© {new Date().getFullYear()} reports-blog</small>,
};

export default config;

3) Структура
content/
  blog/
    2025-09-10-public-post.mdx
    2025-09-01-private-note.md
pages/
  index.tsx
  all/index.tsx             ← закрыть Zero Trust
  n/[slug].tsx              ← закрыть Zero Trust
  api/private/backlinks.ts  ← закрыть Zero Trust
  api/private/slugs.ts      ← закрыть Zero Trust
  blog/                     ← генерится
  private/                  ← генерится
components/
  Backlinks.tsx
public/
  index-public.json
  backlinks-public.json
  slugs-public.json
.data/
  index-all.json
  backlinks-all.json
  slugs-all.json
scripts/
  sync-content.mjs


Создай пустую папку .data в корне (или скрипт сам создаст).

4) Примеры контента

content/blog/2025-09-10-public-post.mdx

---
title: "Публичный пост"
description: "Описание"
date: 2025-09-10
tags: ["pub", "demo"]
status: public
---

Это публичный пост. Ссылка на приват: [[2025-09-01-private-note]].


content/blog/2025-09-01-private-note.md

---
title: "Приватная заметка"
date: 2025-09-01
tags: ["private", "zk"]
# status не указан → будет private по умолчанию
---

Эта заметка приватная. Ссылка на публичный пост: [[2025-09-10-public-post]].

5) Компонент бэклинков (умеет public/all)

components/Backlinks.tsx

'use client';

import { useEffect, useState } from 'react';

type BacklinksMap = Record<string, string[]>;
type SlugInfo = Record<string, { path: string; title: string }>;

export function Backlinks({ slug, scope }: { slug: string; scope: 'public' | 'all' }) {
  const [backlinks, setBacklinks] = useState<string[]>([]);
  const [slugsInfo, setSlugsInfo] = useState<SlugInfo>({});

  useEffect(() => {
    async function load() {
      if (scope === 'public') {
        const [bl, s] = await Promise.all([
          fetch('/backlinks-public.json').then(r => r.json()),
          fetch('/slugs-public.json').then(r => r.json()),
        ]);
        setBacklinks((bl as BacklinksMap)[slug] || []);
        setSlugsInfo(s as SlugInfo);
      } else {
        // приватные данные — через защищённый API
        const [bl, s] = await Promise.all([
          fetch(`/api/private/backlinks?slug=${encodeURIComponent(slug)}`).then(r => r.json()),
          fetch('/api/private/slugs').then(r => r.json()),
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
          return (
            <li key={b}>
              <a href={href}>{title}</a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

6) Публичный индекс /

pages/index.tsx

import { useEffect, useState } from 'react';

type Item = {
  slug: string;
  path: string;
  title: string;
  date?: string | null;
  tags: string[];
  category?: string | null;
};

export default function Home() {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => {
    fetch('/index-public.json').then(r => r.json()).then(setItems);
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-bold mb-4">Публичные статьи</h1>
      <ul className="list-disc ml-5">
        {items.map(i => (
          <li key={i.slug}>
            <a href={i.path}>{i.title}</a>
            {i.date ? <span className="opacity-70"> — {i.date}</span> : null}
            {i.tags?.length ? <span className="opacity-70"> — {i.tags.join(', ')}</span> : null}
          </li>
        ))}
      </ul>
      <p className="mt-6">
        Полный индекс (доступ только с правами): <a href="/all">/all</a>
      </p>
    </main>
  );
}

7) Полный индекс /all (SSR, читает /.data/index-all.json)

pages/all/index.tsx

import type { GetServerSideProps } from 'next';
import fs from 'node:fs';
import path from 'node:path';

type Item = {
  slug: string;
  path: string;
  title: string;
  date?: string | null;
  tags: string[];
  status: 'public' | 'private';
};

export const getServerSideProps: GetServerSideProps = async () => {
  const file = path.join(process.cwd(), '.data', 'index-all.json');
  const raw = fs.readFileSync(file, 'utf-8');
  const items: Item[] = JSON.parse(raw);
  return { props: { items } };
};

export default function All({ items }: { items: Item[] }) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-bold mb-4">Все статьи (public + private)</h1>
      <ul className="list-disc ml-5">
        {items.map(i => (
          <li key={i.slug}>
            <a href={i.path}>{i.title}</a>
            {i.date ? <span className="opacity-70"> — {i.date}</span> : null}
            <span className="ml-2 text-xs px-2 py-0.5 rounded"
              style={{ background: i.status === 'private' ? '#fde68a' : '#bbf7d0' }}>
              {i.status}
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}


Закрой /all в Cloudflare Zero Trust.

8) Универсальный резолвер /n/[slug] (SSR, читает /.data/slugs-all.json)

pages/n/[slug].tsx

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

export default function NSlug() { return null; }


Обязательно закрой /n/* в Zero Trust, чтобы не светить факт существования приватных слагов.

9) Приватные API-роуты (для приватных бэклинков и слуг-карты)

pages/api/private/backlinks.ts

import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'node:fs';
import path from 'node:path';

type BacklinksMap = Record<string, string[]>;

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const slug = String(req.query.slug || '');
    const file = path.join(process.cwd(), '.data', 'backlinks-all.json');
    const data: BacklinksMap = JSON.parse(fs.readFileSync(file, 'utf-8'));
    res.status(200).json(data[slug] || []);
  } catch (e) {
    res.status(200).json([]);
  }
}


pages/api/private/slugs.ts

import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'node:fs';
import path from 'node:path';

export default function handler(_req: NextApiRequest, res: NextApiResponse) {
  try {
    const file = path.join(process.cwd(), '.data', 'slugs-all.json');
    const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
    res.status(200).json(data);
  } catch (e) {
    res.status(200).json({});
  }
}


Закрой /api/private/* в Cloudflare Zero Trust.

10) Sync-скрипт (полностью)

scripts/sync-content.mjs

import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';

const ROOT = process.cwd();
const CONTENT_DIR = path.join(ROOT, 'content', 'blog');
const PAGES_BLOG_DIR = path.join(ROOT, 'pages', 'blog');
const PAGES_PRIV_DIR = path.join(ROOT, 'pages', 'private');
const PUBLIC_DIR = path.join(ROOT, 'public');
const DATA_DIR = path.join(ROOT, '.data');

ensureDir(PAGES_BLOG_DIR);
ensureDir(PAGES_PRIV_DIR);
ensureDir(PUBLIC_DIR);
ensureDir(DATA_DIR);

const exts = new Set(['.md', '.mdx']);
const docs = [];            // {slug,title,description,date,tags,category,status,links:[]}
const forward = new Map();  // slug -> Set(slug)

walk(CONTENT_DIR);

function walk(dir) {
  if (!fs.existsSync(dir)) return;
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p);
    else if (exts.has(path.extname(name))) processDoc(p);
  }
}

function slugifyBase(base) {
  return base
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9-_]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}

function extractSlugFromFilename(filename) {
  const base = path.basename(filename).replace(/\.(md|mdx)$/i, '');
  return slugifyBase(base);
}

function parseLinks(md) {
  const re = /\[\[([^[\]]+?)\]\]/g;
  const links = [];
  let m;
  while ((m = re.exec(md))) links.push(m[1].trim());
  return links;
}

function replaceWikiLinks(md) {
  return md.replace(/\[\[([^[\]]+?)\]\]/g, (_m, s1) => {
    const target = s1.trim();
    const to = `/n/${slugifyBase(target)}`;
    return `[${target}](${to})`;
  });
}

function processDoc(filePath) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  const slug = slugifyBase(data.slug || extractSlugFromFilename(filePath));
  const doc = {
    slug,
    title: data.title || slug,
    description: data.description || '',
    date: data.date || null,
    tags: Array.isArray(data.tags) ? data.tags : [],
    category: data.category || null,
    status: (data.status === 'public' || data.status === 'private') ? data.status : 'private',
    links: parseLinks(content).map(slugifyBase),
    __src: filePath,
  };
  docs.push(doc);

  if (!forward.has(doc.slug)) forward.set(doc.slug, new Set());
  for (const l of doc.links) forward.get(doc.slug).add(l);
}

// backlinks
const backlinksAll = {};
for (const { slug } of docs) backlinksAll[slug] = [];
for (const [from, set] of forward.entries()) {
  for (const to of set) {
    if (backlinksAll[to]) backlinksAll[to].push(from);
  }
}

// public-only backlinks (убираем приватные узлы и связи)
const isPublic = (slug) => docs.find(d => d.slug === slug)?.status === 'public';
const backlinksPublic = {};
for (const d of docs.filter(x => x.status === 'public')) {
  const incoming = (backlinksAll[d.slug] || []).filter(isPublic);
  backlinksPublic[d.slug] = incoming;
}

// emit MDX pages
for (const d of docs) {
  const targetDir = d.status === 'public' ? PAGES_BLOG_DIR : PAGES_PRIV_DIR;
  const outPath = path.join(targetDir, `${d.slug}.mdx`);

  const raw = fs.readFileSync(d.__src, 'utf-8');
  const parsed = matter(raw);
  const fm = {
    ...parsed.data,
    slug: d.slug,
    title: d.title,
    description: d.description,
    date: d.date,
    tags: d.tags,
    category: d.category,
    status: d.status
  };

  const transformed = replaceWikiLinks(parsed.content);

  const headRobots = d.status === 'private'
    ? `\nimport Head from 'next/head'\n<Head><meta name="robots" content="noindex,nofollow"/></Head>\n`
    : '';

  const backlinksImport = `\nimport { Backlinks } from '../../components/Backlinks'\n`;
  const scope = d.status === 'public' ? 'public' : 'all';

  const body =
`---
${stringifyFrontmatter(fm)}---
${headRobots}${backlinksImport}
${transformed}

<Backlinks slug="${d.slug}" scope="${scope}" />
`;

  fs.writeFileSync(outPath, body, 'utf-8');
}

// indices & slugs
const indexPublic = [];
const indexAll = [];
const slugsPublic = {};
const slugsAll = {};

for (const d of docs) {
  const pathOut = d.status === 'public' ? `/blog/${d.slug}` : `/private/${d.slug}`;

  const base = {
    slug: d.slug,
    path: pathOut,
    title: d.title,
    date: d.date,
    tags: d.tags,
    category: d.category || null
  };

  if (d.status === 'public') {
    indexPublic.push(base);
    slugsPublic[d.slug] = { path: pathOut, title: d.title };
  }
  indexAll.push({ ...base, status: d.status });
  slugsAll[d.slug] = { path: pathOut, title: d.title };
}

const sortByDateDesc = (a, b) => String(b.date || '').localeCompare(String(a.date || ''));
indexPublic.sort(sortByDateDesc);
indexAll.sort(sortByDateDesc);

// write public JSON
writeJSON(path.join(PUBLIC_DIR, 'index-public.json'), indexPublic);
writeJSON(path.join(PUBLIC_DIR, 'backlinks-public.json'), backlinksPublic);
writeJSON(path.join(PUBLIC_DIR, 'slugs-public.json'), slugsPublic);

// write private JSON (not public)
writeJSON(path.join(DATA_DIR, 'index-all.json'), indexAll);
writeJSON(path.join(DATA_DIR, 'backlinks-all.json'), backlinksAll);
writeJSON(path.join(DATA_DIR, 'slugs-all.json'), slugsAll);

console.log(`Synced ${docs.length} docs. public=${indexPublic.length}, private=${indexAll.length - indexPublic.length}`);

function ensureDir(d) {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}
function writeJSON(p, obj) {
  fs.writeFileSync(p, JSON.stringify(obj, null, 2), 'utf-8');
}
function stringifyFrontmatter(obj) {
  const lines = [];
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) lines.push(`${k}: [${v.map(x => JSON.stringify(x)).join(', ')}]`);
    else if (v === null) lines.push(`${k}:`);
    else if (typeof v === 'string') lines.push(`${k}: ${JSON.stringify(v)}`);
    else lines.push(`${k}: ${v}`);
  }
  return lines.join('\n') + '\n';
}

Что закрыть в Cloudflare Zero Trust

Добавь политики Require (email/SSO/…) для путей:

/private/*

/all*

/n/*

/api/private/*

Публичными остаются:

/

/blog/*

/index-public.json

/backlinks-public.json

/slugs-public.json

статические ассеты Next.js

Как это использовать

Сложи заметки в content/blog.

Указывай status: public там, что хочешь открыть миру; остальное — приватно по умолчанию.

pnpm dev (скрипт sync отработает, страницы и индексы соберутся).

Настрой Cloudflare Access на перечисленные приватные пути.


