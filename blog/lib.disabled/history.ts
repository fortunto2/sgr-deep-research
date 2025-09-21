import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

const ROOT = process.cwd();
const CONTENT_DIR = path.join(ROOT, 'content');
const SLUGS_FILE = path.join(ROOT, '.data', 'slugs-all.json');

const MARKDOWN_EXTS = new Set(['.md', '.mdx']);

type SlugsAllEntry = {
  path: string;
  title: string;
  language?: string;
  canonical?: string;
};

type SlugsAllMap = Record<string, SlugsAllEntry>;

export function resolveSlug(inputSlug: string): {
  canonical: string;
  entry: SlugsAllEntry | undefined;
  slugs: SlugsAllMap;
} {
  const slugs = readSlugsAll();
  const entry = slugs[inputSlug];
  const canonical = entry?.canonical ?? inputSlug;
  return { canonical, entry, slugs };
}

export function locateContentFile(slug: string): string | null {
  let found: string | null = null;

  function walk(dir: string) {
    if (found) return;
    if (!fs.existsSync(dir)) return;
    for (const name of fs.readdirSync(dir)) {
      const full = path.join(dir, name);
      const stat = fs.statSync(full);
      if (stat.isDirectory()) {
        walk(full);
      } else if (MARKDOWN_EXTS.has(path.extname(name))) {
        const base = path.basename(name, path.extname(name));
        if (base === slug) {
          found = full;
          return;
        }
      }
    }
  }

  walk(CONTENT_DIR);
  return found;
}

export function getGitHistory(filePath: string, limit = 20): Array<{
  sha: string;
  date: string;
  author: string;
  subject: string;
}> {
  const maxCount = Number.isFinite(limit) ? Math.max(1, Math.min(Number(limit), 100)) : 20;
  const relativePath = toGitPath(filePath);
  try {
    const output = execSync(
      `git --no-pager log --pretty=format:%H%x01%ad%x01%an%x01%s --date=iso --max-count=${maxCount} -- "${relativePath}"`,
      { cwd: ROOT, stdio: ['ignore', 'pipe', 'ignore'] }
    ).toString();
    if (!output.trim()) return [];
    return output
      .trim()
      .split('\n')
      .map((line) => {
        const [sha, date, author, subject] = line.split('\x01');
        return { sha, date, author, subject };
      });
  } catch (error) {
    return [];
  }
}

export function getGitContent(filePath: string, ref: string): string | null {
  const relativePath = toGitPath(filePath);
  try {
    return execSync(`git show ${ref}:${relativePath}`, { cwd: ROOT, stdio: ['ignore', 'pipe', 'ignore'] }).toString();
  } catch (error) {
    return null;
  }
}

export function getGitDiff(filePath: string, fromRef: string, toRef: string): string | null {
  const relativePath = toGitPath(filePath);
  try {
    return execSync(`git --no-pager diff ${fromRef} ${toRef} -- "${relativePath}"`, {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'ignore'],
    }).toString();
  } catch (error) {
    return null;
  }
}

function readSlugsAll(): SlugsAllMap {
  if (!fs.existsSync(SLUGS_FILE)) return {};
  try {
    const raw = fs.readFileSync(SLUGS_FILE, 'utf-8');
    return JSON.parse(raw) as SlugsAllMap;
  } catch (error) {
    return {};
  }
}

function toGitPath(filePath: string): string {
  return path.relative(ROOT, filePath).replace(/\\/g, '/');
}
