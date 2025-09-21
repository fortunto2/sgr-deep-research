ратко: чисто клиентский рендер (CSR) ≈ «видит Google, но хуже/медленнее; многие краулеры и превью-боты — частично/плохо». Для нормального SEO лучше отдавать готовый HTML на запросе (SSR/Edge) + корректные <meta>, canonical, sitemap. Это можно сделать без ребилдов и не храня индексы в JSON: мы всё равно тянем сырой .md из S3/Git и просто рендерим его на сервере при запросе — и кладём в кэш Cloudflare.

Ниже — рабочий план и минимальные куски кода, чтобы «оболочка на Next» осталась, публикация шла просто заливкой .md в S3/Git, а SEO стал нормальным.

Что делаем для SEO

SSR/Edge-рендер Markdown для публичных страниц

Для /n/[slug] делаем Server Component (без use client): на запросе тянем .md из S3/Git и рендерим в HTML на сервере.

Кладём ответ в Edge-кэш Cloudflare (через заголовки) — чтобы не бить S3/Git на каждый хит.

Мета-теги из frontmatter

Извлекаем title, description, date, tags, cover (если есть) → <title>, <meta name="description">, og:*, twitter:*, article:published_time.

robots/noindex

Публичные: индексируемые.

Приватные (или не из «своего домена»): отдаём noindex, nofollow и/или закрываем домен Cloudflare Access.

Canonical для мультидомена

Если одна и та же заметка может открыться на нескольких доменах — ставим <link rel="canonical" href="https://{правильный-домен}/n/{slug}"> по полю domain (из frontmatter) или по текущему Host.

Sitemap/robots без JSON-индекса

Раз у тебя MOC/индекс — это Markdown, можно:
а) завести простую sitemap.txt (поддерживать руками — норм для мини-сайтов), или
б) сделать app/sitemap/route.ts, который на лету скачивает твой MOC-Markdown и вытаскивает из него [[wikilink]] → формирует sitemap (ниже пример).

Превью-соцсети

og:title/description, og:type=article, og:image (если есть картинка/cover), twitter:card=summary_large_image.

Производительность

Cache-Control: public, max-age=0, s-maxage=86400, stale-while-revalidate=604800 для HTML.

Уважать ETag/If-None-Match GitHub/S3 (получишь 304).

В S3/R2 — включи CORS GET.

Код: SSR-страница заметки (без редеплоя)

Это замена твоей клиентской версии. Теперь /n/[slug] — серверный рендер: тянем .md по базовым URL, парсим простейший frontmatter, рендерим через markdown-it, выставляем мета-теги и кэш-заголовки. Ни один .md не входит в билд.

app/n/[slug]/page.tsx

import type { Metadata } from 'next';
import MarkdownIt from 'markdown-it';
import { headers } from 'next/headers';

const BASES = (process.env.NEXT_PUBLIC_MD_BASES || '')
  .split(';').map(s => s.trim()).filter(Boolean);

async function fetchMd(slug: string) {
  const re = /^[-a-z0-9_:.]+$/; // простой санитайзер
  const safe = slug.toLowerCase();
  if (!re.test(safe)) throw new Error('Bad slug');

  for (const base of BASES) {
    const url = `${base.replace(/\/+$/,'')}/${encodeURIComponent(safe)}.md`;
    const res = await fetch(url, {
      redirect: 'follow',
      // важное: проксируй кеш CDN/Edge, но не кэшируй в браузере
      next: { revalidate: 0 }
    });
    if (res.ok) {
      const text = await res.text();
      // пробросим etag/last-modified если надо в метаданные
      return { text, sourceUrl: url, etag: res.headers.get('etag') ?? undefined };
    }
  }
  return null;
}

function parseFrontmatter(md: string) {
  const m = md.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n?/);
  const data: Record<string,string> = {};
  let body = md;
  if (m) {
    const fm = m[1];
    body = md.slice(m[0].length);
    for (const line of fm.split(/\r?\n/)) {
      const mm = line.match(/^\s*([a-zA-Z0-9_-]+)\s*:\s*(.*)\s*$/);
      if (mm) {
        const k = mm[1];
        let v = mm[2].trim();
        v = v.replace(/^["']|["']$/g, '');
        data[k] = v;
      }
    }
  }
  return { data, body };
}

const mdIt = new MarkdownIt({ html: false, linkify: true, breaks: false });
// wikilinks [[slug]] -> /n/slug
const orig = mdIt.renderer.rules.text ?? ((t:any,i:number)=>t[i].content);
const wikire = /\[\[([^[\]]+?)\]\]/g;
mdIt.renderer.rules.text = (tokens:any, idx:number, opts:any, env:any, self:any) => {
  const tk = tokens[idx];
  tk.content = tk.content.replace(wikire, (_m, s1) => {
    const slug = String(s1).trim().toLowerCase();
    return `[${s1}](/n/${encodeURIComponent(slug)})`;
  });
  return orig(tokens, idx, opts, env, self);
};

export async function generateMetadata(
  { params }: { params: { slug: string } }
): Promise<Metadata> {
  const host = headers().get('host') || '';
  const found = await fetchMd(params.slug);
  if (!found) return { robots: { index: false, follow: false } };

  const { data } = parseFrontmatter(found.text);
  const title = data.title || params.slug;
  const description = data.description || undefined;
  const domain = data.domain || null;
  const canonicalHost = domain || host;
  const url = `https://${canonicalHost}/n/${params.slug}`;

  const isPrivate = (data.status || '').toLowerCase() !== 'public';
  const robots = isPrivate ? { index: false, follow: false } : { index: true, follow: true };

  const ogImage = data.cover || undefined;

  return {
    title,
    description,
    alternates: { canonical: url },
    robots,
    openGraph: {
      type: 'article',
      url,
      title,
      description,
      images: ogImage ? [{ url: ogImage }] : undefined
    },
    twitter: {
      card: ogImage ? 'summary_large_image' : 'summary',
      title, description,
      images: ogImage ? [ogImage] : undefined
    },
    other: {
      // подсказка CDN: кэшируй на Edge, но не в браузере
      'Cache-Control': 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800'
    }
  };
}

export default async function Page({ params }: { params: { slug: string } }) {
  const host = headers().get('host') || '';
  const found = await fetchMd(params.slug);
  if (!found) {
    return <main><h1>404</h1><p>Не найдено</p></main>;
  }
  const { data, body } = parseFrontmatter(found.text);

  // доменная сегрегация: если frontmatter.domain задан и он не равен текущему host — noindex + 404 для SEO
  if (data.domain && data.domain !== host) {
    return <main><h1>404</h1><p>Не найдено</p></main>;
  }

  // приват: на всякий случай не светим, даже если доступ открыт (главное — CF Access)
  const isPrivate = (data.status || '').toLowerCase() !== 'public';
  // рендерим HTML
  const html = mdIt.render(body);

  return (
    <main>
      <a href="/" style={{opacity:.7}}>&larr; Индекс</a>
      <h1 style={{margin:'12px 0'}}>{data.title || params.slug}</h1>
      {data.date ? <p><small>{data.date}</small></p> : null}
      {/* можно добавить <meta name="robots"> через Metadata API выше */}
      <article className="prose" dangerouslySetInnerHTML={{ __html: html }} />
      {isPrivate ? <p style={{opacity:.6, marginTop:16}}>noindex</p> : null}
    </main>
  );
}


кэш на Edge (Cloudflare Pages): выше мы выставили s-maxage в metadata.other — Next не проставит заголовок сам. В Pages Functions/Worker можно форсировать (см. ниже), но часто хватает CDN-правил по пути /n/*.

Sitemap, robots без JSON

A) ручной способ (просто и надёжно):

кладёшь public/robots.txt и public/sitemap.txt, которые редактируешь как и MOC.

robots.txt:

User-agent: *
Allow: /
Disallow: /all
Sitemap: https://example.com/sitemap.txt


B) динамический sitemap из твоего MOC-Markdown
(скачиваем home.md, вынимаем [[wikilink]], строим URLs):

app/sitemap/route.ts

import { NextResponse } from 'next/server';

export async function GET() {
  const indexUrl = process.env.NEXT_PUBLIC_INDEX_URL!;
  const res = await fetch(indexUrl, { redirect: 'follow', next: { revalidate: 0 } });
  if (!res.ok) return NextResponse.json({ error: 'index fetch failed' }, { status: 500 });
  const md = await res.text();
  const links = Array.from(md.matchAll(/\[\[([^[\]]+?)\]\]/g)).map(m => String(m[1]).trim().toLowerCase());
  const host = process.env.NEXT_PUBLIC_SITE_HOST || 'example.com';
  const urls = Array.from(new Set(links)).map(slug => `https://${host}/n/${encodeURIComponent(slug)}`);

  const body = urls.join('\n') + '\n';
  return new NextResponse(body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=0, s-maxage=3600'
    }
  });
}

Cloudflare: что включить

Pages: деплой как обычно; в Env задать NEXT_PUBLIC_INDEX_URL, NEXT_PUBLIC_MD_BASES, (опц.) NEXT_PUBLIC_SITE_HOST.

Caching Rules: для /n/* выстави Edge TTL = 1 день, Browser TTL = 0, Respect origin: off (или оставь origin-заголовки, если пробрасываешь их из Worker).

Access (Zero Trust): закрой приватные домены/пути (например, весь домен private.example.com или /all).

CORS на S3/R2: разреши GET со своего домена.

Итого

Без редеплоя: новые .md появились в S3/Git → бот пришёл → получил уже готовый HTML (SSR) → индексация норм.

Без JSON-индекса: навигация через твой markdown-индекс (MOC), а sitemap можно держать просто в sitemap.txt или собирать из MOC на лету.

Мультидомен и приватность: соблюдаем через domain в frontmatter + Cloudflare Access/кэш/каноникал.

если хочешь — докину кусок Pages Function/Worker, который принудительно добавляет Cache-Control/ETag к SSR-ответам, и пример robots.txt/sitemap.txt для мультидоменной конфигурации.