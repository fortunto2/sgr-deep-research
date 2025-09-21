'use client';

import { useEffect, useState } from 'react';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt();

interface NoteClientProps {
  slug: string;
}

export default function NoteClient({ slug }: NoteClientProps) {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchContent = async () => {
      try {
        setLoading(true);
        // Try multiple endpoints for R2 access
        let response;
        const endpoints = [
          `https://pub-ff9e4624d5814320a835cd2dcc3be262.r2.dev/${slug}.md`,
          `/content/${slug}.md`
        ];

        for (const endpoint of endpoints) {
          try {
            response = await fetch(endpoint);
            if (response.ok) break;
          } catch (e) {
            continue;
          }
        }

        if (!response || !response.ok) {
          throw new Error(`Note not found: ${slug}`);
        }

        const markdownText = await response.text();

        // Process wikilinks [[note-name]] -> /n/note-name
        const processedMarkdown = markdownText.replace(
          /\[\[([^\]]+)\]\]/g,
          (_, noteName) => {
            const slug = noteName.toLowerCase().replace(/\s+/g, '-');
            return `[${noteName}](/n/${slug})`;
          }
        );

        const htmlContent = md.render(processedMarkdown);
        setContent(htmlContent);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load note');
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [slug]);

  if (loading) {
    return <div className="prose">Загрузка...</div>;
  }

  if (error) {
    return (
      <div className="prose">
        <h1>Ошибка</h1>
        <p>{error}</p>
        <a href="/">← Вернуться на главную</a>
      </div>
    );
  }

  return (
    <div className="prose">
      <a href="/">← Вернуться на главную</a>
      <div dangerouslySetInnerHTML={{ __html: content }} />
    </div>
  );
}