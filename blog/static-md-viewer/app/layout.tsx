export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Static Markdown Viewer</title>
      </head>
      <body style={{ maxWidth: 860, margin: '0 auto', padding: '2rem', fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif', lineHeight: 1.55 }}>
        {children}
      </body>
    </html>
  );
}