import { test } from 'node:test';
import assert from 'node:assert';
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

function readJSON(relPath) {
  const file = path.join(ROOT, relPath);
  return JSON.parse(fs.readFileSync(file, 'utf-8'));
}

function readFile(relPath) {
  const file = path.join(ROOT, relPath);
  return fs.readFileSync(file, 'utf-8');
}

function slugifyBase(base) {
  return base
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9-_]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}

test('sync script maintains Zettelkasten invariants', async () => {
  execSync('node scripts/sync-content.mjs', { cwd: ROOT, stdio: 'pipe' });

  const indexAll = readJSON('.data/index-all.json');
  const publicIndex = readJSON('public/index-public.json');
  const slugsPublic = readJSON('public/slugs-public.json');
  const slugsAll = readJSON('.data/slugs-all.json');
  const backlinksPublic = readJSON('public/backlinks-public.json');
  const backlinksAll = readJSON('.data/backlinks-all.json');

  assert.ok(Array.isArray(indexAll) && indexAll.length > 0, 'index-all should have entries');

  const publicSlugs = new Set(publicIndex.map((item) => item.slug));
  const privateSlugs = new Set(indexAll.filter((item) => item.status === 'private').map((item) => item.slug));

  assert.strictEqual(publicIndex.length, indexAll.filter((item) => item.status === 'public').length, 'public index shows all public notes');

  for (const item of indexAll) {
    const { slug, status, language, aliases = [] } = item;
    assert.ok(typeof language === 'string' && language.length > 0, `language is present for ${slug}`);

    const dir = status === 'public' ? 'blog' : 'private';
    const mdxPath = path.join(ROOT, 'pages', dir, `${slug}.mdx`);
    assert.ok(fs.existsSync(mdxPath), `generated MDX exists for ${slug}`);
    const page = readFile(path.join('pages', dir, `${slug}.mdx`));

    if (status === 'public') {
      assert.ok(publicSlugs.has(slug), `public slug ${slug} recorded in index`);
      assert.ok(slugsPublic[slug], `public slug ${slug} exported to public slugs`);
      assert.ok(page.includes('scope="public"'), `public page ${slug} renders public backlinks scope`);
      assert.ok(!page.includes('noindex'), `public page ${slug} must be indexable`);
    } else {
      assert.ok(!publicSlugs.has(slug), `private slug ${slug} withheld from public index`);
      assert.ok(!slugsPublic[slug], `private slug ${slug} not leaked to slugs-public`);
      assert.ok(page.includes('noindex'), `private page ${slug} sets noindex`);
      assert.ok(page.includes('scope="all"'), `private page ${slug} renders private backlinks scope`);
    }

    const slugInfo = slugsAll[slug];
    assert.ok(slugInfo, `slug ${slug} has entry in slugs-all`);
    assert.strictEqual(slugInfo.canonical, slug, `canonical slug recorded for ${slug}`);

    for (const alias of aliases) {
      const aliasSlug = slugifyBase(alias);
      const aliasInfo = slugsAll[aliasSlug];
      assert.ok(aliasInfo, `alias ${alias} registered in slugs-all`);
      assert.strictEqual(aliasInfo.canonical, slug, `alias ${alias} points to ${slug}`);
    }
  }

  // Backlinks invariants
  for (const [slug, targets] of Object.entries(backlinksPublic)) {
    assert.ok(publicSlugs.has(slug), `public backlinks only for public slug ${slug}`);
    for (const ref of targets) {
      assert.ok(publicSlugs.has(ref), `public backlink ${ref} is public`);
    }
  }

  const canonicalSlugs = new Set(indexAll.map((item) => item.slug));
  for (const slug of Object.keys(backlinksAll)) {
    assert.ok(canonicalSlugs.has(slug), `backlinks-all key ${slug} belongs to a canonical slug`);
  }
});
