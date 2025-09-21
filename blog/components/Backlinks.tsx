// Simplified Backlinks component for static export
export function Backlinks({ slug, scope }: { slug: string; scope: 'public' | 'all' }) {
  return (
    <section style={{ marginTop: '3rem' }}>
      <h3>Обратные ссылки</h3>
      <p>
        <em>Обратные ссылки будут доступны после настройки API</em>
      </p>
    </section>
  );
}