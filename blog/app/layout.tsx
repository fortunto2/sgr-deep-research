import type { ReactNode } from 'react';

export const metadata = {
  title: 'reports-blog',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
