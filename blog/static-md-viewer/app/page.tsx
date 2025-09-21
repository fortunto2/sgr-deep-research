export default function HomePage() {
  return (
    <div className="prose">
      <h1>Static Markdown Viewer</h1>
      <p>Добро пожаловать в статический просмотрщик markdown файлов.</p>
      <p>Этот сайт загружает контент динамически из Cloudflare R2 storage.</p>
      <h2>Примеры заметок:</h2>
      <ul>
        <li><a href="/n/welcome">Добро пожаловать</a></li>
        <li><a href="/n/about">О проекте</a></li>
        <li><a href="/n/test">Тестовая заметка</a></li>
        <li><a href="/n/20250920-120000-bashkir-moc">Башкирский knowledge graph</a></li>
        <li><a href="/n/20250915-223103-istoriya-bashkir-i-blizkih-k-nim-narodov-etnogenez-g">История башкир и этногенез</a></li>
        <li><a href="/n/20250916-020705-salavat-yulaev-biograficheskaya-spravka-i-istoriko-ku">Салават Юлаев - биография</a></li>
        <li><a href="/n/20250917-093944-kak-bashkiry-tradicionno-gotovyat-kumys-tehnologiya-u">Как башкиры готовят кумыс</a></li>
      </ul>
    </div>
  );
}