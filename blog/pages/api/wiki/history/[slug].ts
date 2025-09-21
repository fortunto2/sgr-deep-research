import type { NextApiRequest, NextApiResponse } from 'next';
import path from 'node:path';
import {
  resolveSlug,
  locateContentFile,
  getGitHistory,
  getGitContent,
  getGitDiff,
} from '../../../../lib/history';

type HistoryResponse = {
  requestedSlug: string;
  slug: string;
  file: string;
  commits: Array<{
    sha: string;
    date: string;
    author: string;
    subject: string;
  }>;
  meta?: {
    title?: string;
    path?: string;
    language?: string;
  };
  content?: string | null;
  diff?: string | null;
};

export default function handler(req: NextApiRequest, res: NextApiResponse<HistoryResponse | { error: string }>) {
  const slugParam = req.query.slug;
  if (Array.isArray(slugParam) || !slugParam?.trim()) {
    return res.status(400).json({ error: 'Missing slug' });
  }

  const { canonical, entry } = resolveSlug(slugParam);
  const filePath = locateContentFile(canonical);
  if (!filePath) {
    return res.status(404).json({ error: `Note not found for slug ${slugParam}` });
  }

  const limitParam = req.query.limit;
  const limit = Array.isArray(limitParam) ? parseInt(limitParam[0] ?? '20', 10) : parseInt(limitParam ?? '20', 10);

  const commits = getGitHistory(filePath, Number.isNaN(limit) ? 20 : limit);
  const response: HistoryResponse = {
    requestedSlug: slugParam,
    slug: canonical,
    file: path.relative(process.cwd(), filePath),
    commits,
    meta: entry ? { title: entry.title, path: entry.path, language: entry.language } : undefined,
  };

  const refParam = req.query.ref;
  if (typeof refParam === 'string' && refParam) {
    response.content = getGitContent(filePath, refParam);
  }

  const fromParam = req.query.from;
  const toParam = req.query.to;
  if (typeof fromParam === 'string' && typeof toParam === 'string' && fromParam && toParam) {
    response.diff = getGitDiff(filePath, fromParam, toParam);
  }

  return res.status(200).json(response);
}
