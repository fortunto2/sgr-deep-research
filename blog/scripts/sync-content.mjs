import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';

const ROOT = process.cwd();
const CONTENT_DIR = path.join(ROOT, 'content');
const PAGES_BLOG_DIR = path.join(ROOT, 'pages', 'blog');
const PAGES_PRIV_DIR = path.join(ROOT, 'pages', 'private');
const PUBLIC_DIR = path.join(ROOT, 'public');
const DATA_DIR = path.join(ROOT, '.data');
const SITE_NAME = 'reports-blog';

ensureDir(PAGES_BLOG_DIR);
ensureDir(PAGES_PRIV_DIR);
ensureDir(PUBLIC_DIR);
ensureDir(DATA_DIR);
clearDir(PAGES_BLOG_DIR);
clearDir(PAGES_PRIV_DIR);

const exts = new Set(['.md', '.mdx']);
const docs = [];
const forward = new Map();

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

  const tagsRaw = Array.isArray(data.tags) ? data.tags.slice() : typeof data.tags === 'string' ? [data.tags] : [];
  const fallbackTag = data.tag;
  if (Array.isArray(fallbackTag)) tagsRaw.push(...fallbackTag);
  else if (typeof fallbackTag === 'string') tagsRaw.push(fallbackTag);
  const tags = Array.from(new Set(tagsRaw.map((tag) => String(tag).trim()).filter(Boolean)));
  const aliasesRaw = Array.isArray(data.aliases) ? data.aliases.slice() : typeof data.aliases === 'string' ? [data.aliases] : [];
  const aliases = Array.from(new Set(aliasesRaw.map((alias) => String(alias).trim()).filter(Boolean)));
  const aliasSlugs = Array.from(new Set(aliases.map((alias) => slugifyBase(alias)).filter(Boolean)));
  const language = typeof data.language === 'string' && data.language.trim() ? data.language.trim() : 'ru';

  const slug = slugifyBase(data.slug || extractSlugFromFilename(filePath));
  let date = data.date ?? null;
  if (date instanceof Date) {
    date = date.toISOString().slice(0, 10);
  } else if (typeof date === 'string') {
    date = date.trim();
  } else {
    date = null;
  }

  const doc = {
    slug,
    title: data.title || slug,
    description: data.description || '',
    date,
    tags,
    aliases,
    aliasSlugs,
    category: data.category || null,
    status: (data.status === 'public' || data.status === 'private') ? data.status : 'private',
    language,
    links: parseLinks(content).map(slugifyBase),
    __src: filePath,
  };
  docs.push(doc);

  if (!forward.has(doc.slug)) forward.set(doc.slug, new Set());
  for (const l of doc.links) forward.get(doc.slug).add(l);
}

const aliasToCanonical = new Map();
for (const doc of docs) {
  aliasToCanonical.set(doc.slug, doc.slug);
  for (const alias of doc.aliasSlugs) {
    if (!aliasToCanonical.has(alias)) aliasToCanonical.set(alias, doc.slug);
  }
}
for (const [from, set] of forward.entries()) {
  const normalized = new Set();
  for (const target of set) {
    const canonical = aliasToCanonical.get(target) || target;
    if (canonical) normalized.add(canonical);
  }
  forward.set(from, normalized);
}

const backlinksAll = {};
for (const { slug } of docs) backlinksAll[slug] = [];
for (const [from, set] of forward.entries()) {
  for (const to of set) {
    if (backlinksAll[to]) backlinksAll[to].push(from);
  }
}

const isPublic = (slug) => docs.find((d) => d.slug === slug)?.status === 'public';
const backlinksPublic = {};
for (const d of docs.filter((x) => x.status === 'public')) {
  const incoming = (backlinksAll[d.slug] || []).filter(isPublic);
  backlinksPublic[d.slug] = incoming;
}

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
    aliases: d.aliases,
    category: d.category,
    status: d.status,
    language: d.language,
  };
  delete fm.tag;
  delete fm.aliasSlugs;

  const transformed = replaceWikiLinks(parsed.content);

  const imports = [
    "import Head from 'next/head'",
    "import { Backlinks } from '../../components/Backlinks'",
  ].join('\n');
  const scope = d.status === 'public' ? 'public' : 'all';
  const fullTitle = d.title ? `${d.title} · ${SITE_NAME}` : SITE_NAME;
  const robots = d.status === 'public' ? 'index,follow' : 'noindex,nofollow';
  const metaLines = [
    `<title>${escapeHtml(fullTitle)}</title>`,
    `<meta name="robots" content="${robots}" />`,
    `<meta property="og:title" content="${escapeAttr(d.title)}" />`,
    `<meta property="og:type" content="article" />`,
    `<meta name="twitter:title" content="${escapeAttr(d.title)}" />`,
  ];
  if (d.description) {
    metaLines.splice(1, 0, `<meta name="description" content="${escapeAttr(d.description)}" />`);
    metaLines.push(`<meta property="og:description" content="${escapeAttr(d.description)}" />`);
    metaLines.push(`<meta name="twitter:description" content="${escapeAttr(d.description)}" />`);
  }
  const headMeta = `
<Head>
${metaLines.join('\n')}
</Head>`;

  const dateLine = d.date ? `<p className="text-sm opacity-70"><time dateTime="${d.date}">${escapeHtml(d.date)}</time></p>` : '';
  const tagsLine = d.tags.length ? `<p className="text-sm opacity-70">Теги: ${escapeHtml(d.tags.join(', '))}</p>` : '';
  const categoryLine = d.category ? `<p className="text-sm opacity-70">Категория: ${escapeHtml(d.category)}</p>` : '';
  const headerBlock = `
<header className="mb-8 space-y-2">
  <h1 className="text-3xl font-bold">${escapeHtml(d.title)}</h1>
  ${dateLine}
  ${tagsLine}
  ${categoryLine}
</header>`;

  const body = `---
${stringifyFrontmatter(fm)}---
${imports}
${headMeta}${headerBlock}

${transformed}

<Backlinks slug="${d.slug}" scope="${scope}" />
`;

  fs.writeFileSync(outPath, body, 'utf-8');
}

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
    aliases: d.aliases,
    category: d.category || null,
    language: d.language,
  };

  if (d.status === 'public') {
    indexPublic.push(base);
    slugsPublic[d.slug] = { path: pathOut, title: d.title, language: d.language };
  }
  indexAll.push({ ...base, status: d.status });
  slugsAll[d.slug] = { path: pathOut, title: d.title, language: d.language, canonical: d.slug };
  for (const aliasSlug of d.aliasSlugs) {
    slugsAll[aliasSlug] = { path: pathOut, title: d.title, language: d.language, canonical: d.slug };
  }
}

const sortByDateDesc = (a, b) => String(b.date || '').localeCompare(String(a.date || ''));
indexPublic.sort(sortByDateDesc);
indexAll.sort(sortByDateDesc);

writeJSON(path.join(PUBLIC_DIR, 'index-public.json'), indexPublic);
writeJSON(path.join(PUBLIC_DIR, 'backlinks-public.json'), backlinksPublic);
writeJSON(path.join(PUBLIC_DIR, 'slugs-public.json'), slugsPublic);

writeJSON(path.join(DATA_DIR, 'index-all.json'), indexAll);
writeJSON(path.join(DATA_DIR, 'backlinks-all.json'), backlinksAll);
writeJSON(path.join(DATA_DIR, 'slugs-all.json'), slugsAll);

console.log(`Synced ${docs.length} docs. public=${indexPublic.length}, private=${indexAll.length - indexPublic.length}`);

function clearDir(d) {
  if (!fs.existsSync(d)) return;
  for (const name of fs.readdirSync(d)) {
    const file = path.join(d, name);
    if (fs.statSync(file).isDirectory()) continue;
    if (path.extname(name).toLowerCase() === '.mdx') {
      fs.unlinkSync(file);
    }
  }
}
function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function escapeAttr(value = '') {
  return escapeHtml(value).replace(/'/g, '&#39;');
}
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
    if (Array.isArray(v)) lines.push(`${k}: [${v.map((x) => JSON.stringify(x)).join(', ')}]`);
    else if (v === null) lines.push(`${k}:`);
    else if (typeof v === 'string') lines.push(`${k}: ${JSON.stringify(v)}`);
    else lines.push(`${k}: ${v}`);
  }
  return lines.join('\n') + '\n';
}
