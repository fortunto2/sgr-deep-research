import NoteClient from './note-client';

export async function generateStaticParams() {
  return [
    { slug: 'welcome' },
    { slug: 'about' },
    { slug: 'test' },
    { slug: '20250920-120000-bashkir-moc' },
    { slug: '20250915-223103-istoriya-bashkir-i-blizkih-k-nim-narodov-etnogenez-g' },
    { slug: '20250916-020705-salavat-yulaev-biograficheskaya-spravka-i-istoriko-ku' },
    { slug: '20250917-093944-kak-bashkiry-tradicionno-gotovyat-kumys-tehnologiya-u' }
  ];
}

interface NotePageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function NotePage({ params }: NotePageProps) {
  const { slug } = await params;
  return <NoteClient slug={slug} />;
}