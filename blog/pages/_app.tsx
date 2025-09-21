import type { AppProps } from 'next/app';
import { Layout } from 'nextra-theme-blog';
import Link from 'next/link';
import config from '../theme.config';
import 'nextra-theme-blog/style.css';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <Layout>
      <div className="x:min-h-dvh x:flex x:flex-col x:gap-12">
        <header className="x:py-8 x:border-b x:border-neutral-200 x:dark:border-neutral-800">
          <div className="x:container x:px-4 x:flex x:items-center x:justify-between">
            <Link href="/" className="x:text-xl x:font-semibold">
              {config.name}
            </Link>
          </div>
        </header>
        <main className="x:flex-1">
          <Component {...pageProps} />
        </main>
        <footer className="x:py-10 x:border-t x:border-neutral-200 x:dark:border-neutral-800">
          <div className="x:container x:px-4">{config.footer}</div>
        </footer>
      </div>
    </Layout>
  );
}
