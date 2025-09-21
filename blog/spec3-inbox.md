Inbox для Zettelkasten: правила и реализация
1) Дерево контента
content/
  inbox/                 # входящие (сырые, ещё не разобраны)
    idea-raw-note.md
    link-to-paper.txt    # можно позволить разные форматы
  notes/                 # атомарные заметки (основной «vault»)
    20250921-101530-atomic-idea.md
  indexes/               # MOC/structure notes (оглавления)
    moc-knowledge-graphs.md
  _assets/               # вложения к заметкам
    20250921-101530-atomic-idea/fig1.png


Всё, что в content/inbox/, никогда не публикуется в «публичный блог» и не попадает в открытые JSON.

Inbox виден только тебе: отдельная страница /inbox (SSR), закрытая Cloudflare Zero Trust.

Промоут (разбор): файл из inbox/ переносится в notes/, получает стабильный slug (timestamp), frontmatter и становится полноценной ZK-заметкой.

2) Frontmatter и статусы

В inbox/ frontmatter не обязателен. Любой файл из inbox считается черновиком.

После промоута создаём frontmatter:

---
title: "Коротко о сути"
date: 2025-09-21
tags: []
category:
status: private
---


По умолчанию — private. Публичность — осознанное действие (status: public).

3) Поведение sync

scripts/sync-content.mjs:

обходит content/notes и content/indexes (всё это — «контент»),

обходит content/inbox только для закрытого индекса /inbox; эти файлы не превращаются в /blog/* или /private/*,

строит back-links только из notes/indexes (чтобы сырые не «засоряли» граф),

пишет:

публичные JSON (index-public.json, backlinks-public.json, slugs-public.json) — как раньше,

приватные JSON (.data/index-all.json, .data/backlinks-all.json, .data/slugs-all.json) — как раньше,

список inbox → .data/index-inbox.json.

4) UI: страницы

/ — публичный индекс (как было).

/all — полный индекс (закрыт ZT) — как было.

/inbox — список входящих (закрыт ZT) — новая страница.

/n/[slug] — резолвер (закрыт ZT) — как было.

/blog/*, /private/* — как было.

5) Промоут из inbox → notes

CLI-скрипт scripts/promote.mjs:

принимает путь к файлу в content/inbox,

генерирует slug YYYYMMDD-HHMMSS-title,

добавляет frontmatter (если нет),

переносит в content/notes/<slug>.md,

сохраняет исходный текст без вычищения (минимум магии),

опционально создаёт папку _assets/<slug>/.

Код
5.1 Обновление sync: поддержка inbox

Отредактируй твой scripts/sync-content.mjs (ниже — рабочие добавления/замены ключевых частей; если у тебя уже есть версия из прошлой итерации, просто дополни её указанными блоками).

// ДОБАВЬ сверху новые константы:
const CONTENT_ROOT = path.join(ROOT, 'content');
const NOTES_DIR = path.join(CONTENT_ROOT, 'notes');
const INDEXES_DIR = path.join(CONTENT_ROOT, 'indexes');
const INBOX_DIR = path.join(CONTENT_ROOT, 'inbox');

// ... остальное оставь как есть

// ВМЕСТО одного walk(CONTENT_DIR) сделай так:
const contentFiles = [];
collectFiles(NOTES_DIR, contentFiles);
collectFiles(INDEXES_DIR, contentFiles);

const inboxFiles = [];
collectFiles(INBOX_DIR, inboxFiles); // отдельно собираем inbox, не смешиваем

// обработка контента (notes + indexes)
for (const filePath of contentFiles) {
  processDoc(filePath);
}

// backlinks считаем как раньше на основе docs (только из notes/indexes)
const backlinksAll = {};
for (const { slug } of docs) backlinksAll[slug] = [];
for (const [from, set] of forward.entries()) {
  for (const to of set) {
    if (backlinksAll[to]) backlinksAll[to].push(from);
  }
}

// public-only backlinks
const isPublic = (slug) => docs.find(d => d.slug === slug)?.status === 'public';
const backlinksPublic = {};
for (const d of docs.filter(x => x.status === 'public')) {
  const incoming = (backlinksAll[d.slug] || []).filter(isPublic);
  backlinksPublic[d.slug] = incoming;
}

// emit MDX pages (только для docs из notes/indexes) — как было
for (const d of docs) {
  // ... твоя логика генерации /blog и /private
}

// индексы и слуг-мапы (как было) — для docs

// НИЖЕ: индекс inbox (только список файлов, без публикации)
const inboxIndex = inboxFiles.map(fp => {
  const rel = path.relative(CONTENT_ROOT, fp).replace(/\\/g, '/');
  const base = path.basename(fp);
  return {
    file: rel,      // 'inbox/idea-raw-note.md'
    name: base,     // 'idea-raw-note.md'
    mtime: fs.statSync(fp).mtime.toISOString()
  };
});
writeJSON(path.join(DATA_DIR, 'index-inbox.json'), inboxIndex);

// ===== вспомогалки =====
function collectFiles(dir, out) {
  if (!fs.existsSync(dir)) return;
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) collectFiles(p, out);
    else if (exts.has(path.extname(name))) out.push(p);
  }
}


Важно: processDoc() оставь прежним (он парсит frontmatter, wikilinks и т.д.) — мы просто не вызываем processDoc для файлов из inbox.

5.2 Страница /inbox (закрыть облачной авторизацией)

pages/inbox/index.tsx:

import type { GetServerSideProps } from 'next';
import fs from 'node:fs';
import path from 'node:path';

type InboxItem = { file: string; name: string; mtime: string };

export const getServerSideProps: GetServerSideProps = async () => {
  const p = path.join(process.cwd(), '.data', 'index-inbox.json');
  const raw = fs.existsSync(p) ? fs.readFileSync(p, 'utf-8') : '[]';
  const items: InboxItem[] = JSON.parse(raw);
  // Эту страницу ЗАКРОЙ через Cloudflare Zero Trust
  return { props: { items } };
};

export default function Inbox({ items }: { items: InboxItem[] }) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-bold mb-6">Inbox (входящие)</h1>
      {items.length === 0 ? (
        <p>Пусто</p>
      ) : (
        <ul className="list-disc ml-5">
          {items
            .sort((a,b)=> b.mtime.localeCompare(a.mtime))
            .map(i => (
            <li key={i.file}>
              <code>{i.name}</code>
              <span className="opacity-70"> — {new Date(i.mtime).toLocaleString()}</span>
              {/* Можно добавить кнопку/ссылку на промоут */}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

5.3 Промоутер scripts/promote.mjs
import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';

const ROOT = process.cwd();
const CONTENT_ROOT = path.join(ROOT, 'content');
const INBOX_DIR = path.join(CONTENT_ROOT, 'inbox');
const NOTES_DIR = path.join(CONTENT_ROOT, 'notes');
const ASSETS_DIR = path.join(CONTENT_ROOT, '_assets');

if (process.argv.length < 3) {
  console.error('Usage: node scripts/promote.mjs <inbox-relative-path>');
  process.exit(1);
}

const rel = process.argv[2];
const src = path.join(CONTENT_ROOT, rel);
if (!src.startsWith(INBOX_DIR) || !fs.existsSync(src)) {
  console.error('Source must be inside content/inbox and exist');
  process.exit(1);
}

// читаем исходник
const raw = fs.readFileSync(src, 'utf-8');
const parsed = matter(raw);

// генерим slug
const now = new Date();
const pad = (n) => String(n).padStart(2,'0');
const stamp = `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;

// пробуем извлечь «title» из имени файла
const baseName = path.basename(src).replace(/\.(md|mdx|txt)$/i,'');
const safeTitle = baseName.toLowerCase().replace(/[^a-z0-9-_]+/g,'-').replace(/^-+|-+$/g,'');

const slug = `${stamp}-${safeTitle || 'note'}`;
const dst = path.join(NOTES_DIR, `${slug}.md`);

// собираем frontmatter
const data = {
  title: parsed.data?.title || baseName,
  date: parsed.data?.date || `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`,
  tags: Array.isArray(parsed.data?.tags) ? parsed.data.tags : [],
  category: parsed.data?.category || null,
  status: parsed.data?.status === 'public' ? 'public' : 'private',
};

const body = parsed.content.trim() ? parsed.content.trim() + '\n' : '\n';
const out = matter.stringify(body, data);

// создаём assets-папку
const assetFolder = path.join(ASSETS_DIR, slug);
if (!fs.existsSync(assetFolder)) fs.mkdirSync(assetFolder, { recursive: true });

// пишем файл назначения
fs.writeFileSync(dst, out, 'utf-8');

// удаляем исходник из inbox
fs.unlinkSync(src);

console.log(`Promoted "${rel}" → notes/${slug}.md`);
console.log(`Assets dir: _assets/${slug}/`);


Использование:

pnpm node scripts/promote.mjs inbox/idea-raw-note.md


(или node scripts/promote.mjs inbox/idea-raw-note.md если без alias’а)

После промоута — pnpm dev (sync отработает) и заметка окажется в графе notes, с приватным статусом, готовая к дальнейшей правке/публикации.

Практические заметки

Форматы в inbox: можно разрешить .txt, .md, .mdx. Промоутер приведёт к .md и добавит frontmatter.

«Быстрый захват»: на мобиле кидай текст в content/inbox (через GitHub web, Working Copy, Obsidian Mobile, и т.д.).

Скорость sync: при разрастании vault’а подумай об инкрементальном sync (кэш mtimes/хэшей).

CI-проверки: линт ссылок [[slug]], отсутствующих целей, и «пустых» title.

Гигиена: _assets/<slug>/ держит медиа рядом логически, но физически отдельно — меньше мусора в списке заметок.

получится прям «как по книжке»: быстрый захват в Inbox → осознанная переработка → промоут в Notes (приватно) → при необходимости публикация (status: public) через PR.