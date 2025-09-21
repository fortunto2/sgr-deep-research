крутая идея — “статическая оболочка” на Next, без билда контента и без каких-либо индексов в JSON. Всё хранится как сырой Markdown в S3/R2 или GitHub, а сайт просто:

на главной грузит готовый “индекс-файл” в Markdown (твоя MOC/оглавление) и показывает его как есть;

при открытии заметки по /n/<slug> скачивает <slug>.md напрямую из хранилища и рендерит в браузере;

[[wikilink]] внутри Md переписывает в ссылки вида /n/<slug> прямо на клиенте.

Это значит: ты просто кидаешь новые .md в S3/Repo и правишь одну MOC-страницу (тоже markdown), — и всё появляется на сайте без редеплоя.

Ниже — минимальный, рабочий каркас на Next 15 App Router (Edge не нужен), который делает ровно это. Без Nextra, без серверного рендера контента, без JSON-индексов.

1) Идея резолвинга без индекса

Домашняя страница / берёт один “индексный” markdown по URL из ENV (или по карте домен→URL) и просто отображает его. Ссылки внутри могут вести на /n/<slug> или на внешние .md.

Роут /n/[slug] резолвит “куда сходить за файлом” так:

берёт список “базовых корней” из ENV NEXT_PUBLIC_MD_BASES (через ;), например:

https://raw.githubusercontent.com/you/zk/main/content/notes;
https://raw.githubusercontent.com/you/zk/main/content/indexes;
https://your-r2-bucket.r2.dev/notes


пробует скачать ${base}/${slug}.md поочерёдно до первого удачного ответа (200).

рендерит полученный Markdown на клиенте (markdown-it).

[[wikilink]] → ссылку на /n/<slug>.

итого никакой предварительной “сборки индекса” не требуется. Навигация — через твои MOC-страницы в Markdown.

2) Cloudflare настроить просто

Pages: деплоишь этот Next-проект (ниже код).

Workers/Access (по желанию):

приватные хранилища (R2/S3) закрываешь Cloudflare Access по домену бакета или выдаёшь signed URLs (R2/S3 Presign). Браузер будет скачивать .md уже по защищённой ссылке.

если у тебя несколько мини-сайтов на разных доменах, можно:

задать разные ENV на уровне Cloudflare Pages для каждого домена (индексный URL и базы), или

прокинуть через Worker заголовки/ENV (реже нужно).

CORS: в S3/R2 включи CORS GET с твоего сайта.

3) Код (полностью, без заглушек)
package.json
{
  "name": "md-static-viewer",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "markdown-it": "14.1.0",
    "next": "15.5.3",
    "react": "19.1.0",
    "react-dom": "19.1.0"
  }
}

.env (пример для локали; на Cloudflare Pages задашь переменные в UI)
NEXT_PUBLIC_INDEX_URL=https://raw.githubusercontent.com/you/zk/main/content/indexes/home.md
NEXT_PUBLIC_MD_BASES=https://raw.githubusercontent.com/you/zk/main/content/notes;https://raw.githubusercontent.com/you/zk/main/content/indexes;https://your-r2-bucket.r2.dev/notes

app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body style={{ maxWidth: 860, margin: '0 auto', padding: '2rem' }}>
        {children}
      </body>
    </html>
  );
}

app/globals.css (по желанию, можно пустым оставить)
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.55; }
main a { color: inherit; text-decoration: underline; }
.prose img { max-width: 100%; }

app/page.tsx — главная: грузим markdown-индекс и показываем как есть
'use client';

import { useEffect, useMemo, useState } from 'react';
import MarkdownIt from 'markdown-it';

export default function Home() {
  const [html, setHtml] = useState<string>('');
  const [err, setErr] = useState<string>('');

  const md = useMemo(() => {
    const inst = new MarkdownIt({ html: false, linkify: true, breaks: false });
    // wikilinks [[slug]] -> /n/slug
    const re = /\[\[([^[\]]+?)\]\]/g;
    const orig = inst.renderer.rules.text ?? ((t, i) => t[i].content);
    inst.renderer.rules.text = (tokens, idx, options, env, self) => {
      const tk = tokens[idx];
      tk.content = tk.content.replace(re, (_m, s1) => {
        const slug = String(s1).trim().toLowerCase();
        return `[${s1}](/n/${encodeURIComponent(slug)})`;
      });
      return orig(tokens, idx, options, env, self);
    };
    return inst;
  }, []);

  useEffect(() => {
    const run = async () => {
      const url = process.env.NEXT_PUBLIC_INDEX_URL!;
      const res = await fetch(url, { redirect: 'follow' });
      if (!res.ok) throw new Error(`Index fetch ${res.status}`);
      const raw = await res.text();
      setHtml(md.render(raw));
    };
    run().catch(e => setErr(String(e)));
  }, [md]);

  if (err) return <main><h1>Ошибка</h1><p>{err}</p></main>;

  return (
    <main>
      <h1 style={{marginTop:0}}>Индекс</h1>
      <article className="prose" dangerouslySetInnerHTML={{ __html: html }} />
      <p style={{opacity:.6, marginTop:24}}>
        Поддерживаются wikilinks: <code>[[slug]]</code>
      </p>
    </main>
  );
}

app/n/[slug]/page.tsx — “просмотрщик” конкретной заметки
'use client';

import { useEffect, useMemo, useState } from 'react';
import MarkdownIt from 'markdown-it';

type Found = { url: string } | null;

export default function NotePage({ params }: { params: { slug: string } }) {
  const [err, setErr] = useState<string>('');
  const [title, setTitle] = useState<string>('');
  const [html, setHtml] = useState<string>('');

  const md = useMemo(() => {
    const inst = new MarkdownIt({ html: false, linkify: true, breaks: false });
    const re = /\[\[([^[\]]+?)\]\]/g;
    const orig = inst.renderer.rules.text ?? ((t, i) => t[i].content);
    inst.renderer.rules.text = (tokens, idx, options, env, self) => {
      const tk = tokens[idx];
      tk.content = tk.content.replace(re, (_m, s1) => {
        const slug = String(s1).trim().toLowerCase();
        return `[${s1}](/n/${encodeURIComponent(slug)})`;
      });
      return orig(tokens, idx, options, env, self);
    };
    return inst;
  }, []);

  useEffect(() => {
    const run = async () => {
      const bases = (process.env.NEXT_PUBLIC_MD_BASES || '').split(';').map(s => s.trim()).filter(Boolean);
      if (!bases.length) throw new Error('NEXT_PUBLIC_MD_BASES is empty');
      const slug = params.slug.toLowerCase();

      const tryFetch = async (): Promise<Found> => {
        for (const base of bases) {
          const url = `${base.replace(/\/+$/,'')}/${encodeURIComponent(slug)}.md`;
          const res = await fetch(url, { redirect: 'follow' });
          if (res.ok) return { url };
        }
        return null;
      };

      const found = await tryFetch();
      if (!found) throw new Error('Не найден файл .md для этого slug в базах');

      const raw = await (await fetch(found.url)).text();

      // минимальный парс frontmatter title: "..."
      const fmMatch = raw.match(/^---\s*[\r\n]+([\s\S]*?)\r?\n---\s*[\r\n]+/);
      if (fmMatch) {
        const titleMatch = fmMatch[1].match(/^\s*title:\s*["']?(.+?)["']?\s*$/m);
        if (titleMatch) setTitle(titleMatch[1]);
      }
      setHtml(md.render(raw));
    };
    run().catch(e => setErr(String(e)));
  }, [params.slug, md]);

  if (err) return <main><a href="/" style={{opacity:.7}}>&larr; Индекс</a><h1>Ошибка</h1><p>{err}</p></main>;

  return (
    <main>
      <a href="/" style={{opacity:.7}}>&larr; Индекс</a>
      <h1 style={{margin:'12px 0'}}>{title || params.slug}</h1>
      <article className="prose" dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}


при необходимости добавь ещё один роут /all и просто укажи другой INDEX_URL (например, “закрытый” MOC), а сам путь /all закрой Cloudflare Access’ом. Никакой переcборки не нужно.

4) Где брать “индекс”? — из твоего же MD

Раз у тебя уже есть MOC/индексы в Markdown — просто используй их:

для публичной главной страницы укажи NEXT_PUBLIC_INDEX_URL на публичный home.md (в GitHub Raw или R2).

для полного (приватного) — сделай /all как страницу, которая использует другую переменную, например NEXT_PUBLIC_INDEX_URL_ALL, и закрой этот путь Cloudflare Access’ом.

Следовательно, никаких JSON: “индекс” — это твой markdown-файл.

5) Часто задаваемые нюансы

Как сделать много доменов/мини-сайтов без редеплоя?
На Cloudflare Pages можно задать переменные окружения по домену (или через Worker задать заголовок/вариант). Для домена A укажи свой NEXT_PUBLIC_INDEX_URL и свои NEXT_PUBLIC_MD_BASES, для домена B — другие значения. Оболочка остаётся одна и та же.

GitHub Raw может троттлить?
Если будет большой трафик — можно отдать через jsDelivr (https://cdn.jsdelivr.net/gh/user/repo@branch/path/file.md) или переложить контент в R2/S3 с CDN. Не забудь CORS.

Приватные заметки?

Держи их в R2/S3 под доменом, закрытым Cloudflare Access (или используй подписанные ссылки).

Для публичного домена просто не ставь на них ссылок в публичном MOC.

Wikilinks на заметку с другого “базового корня”?
Если у тебя несколько папок (notes/indexes) — мы их уже перебираем в NEXT_PUBLIC_MD_BASES. Если хочешь тоньше — можно добавить эвристику: пробовать и ${slug}/index.md, и подкаталоги.

Картинки и вложения?
Вставляй обычные markdown-ссылки на https://.../assets/.... Браузер их загрузит напрямую с S3/R2/GitHub. Можно держать _assets/<slug>/....

6) Что делать в Cloudflare (коротко)

Создай проект Pages, деплой этот Next.

В Settings → Environment variables добавь:

NEXT_PUBLIC_INDEX_URL → URL твоего главного MOC

NEXT_PUBLIC_MD_BASES → список баз, разделённых ;
(для другого домена — override переменных).

(Опционально) Access: закрой /all или вообще весь домен “приватного” индекса.

В R2/S3 включи CORS GET с твоего домена.