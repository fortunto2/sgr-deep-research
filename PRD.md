# Product Requirements Document (PRD)

## 1. Цель продукта
Создать публичный веб-блог на Next.js + Nextra 4 для публикации аналитических отчётов SGR. Блог должен:

- показывать главную страницу с описанием проекта и навигацией по категориям;
- позволять просматривать каждый отчёт из каталога `content/posts/`;
- выводить блок «Похожие материалы» и автоматически формировать страницы категорий и поиск.

## 2. Пользовательские сценарии

### 2.1 Гость
- Переходит на `/`, читает вступление, выбирает категорию.
- Открывает конкретный пост из списка (на главной, в категории или через поиск).
- На странице поста читает материал и изучает блок «Похожие материалы».
- Использует встроенный поиск Nextra.

### 2.2 Редактор контента
- Добавляет или обновляет пост в `content/posts/<slug>.mdx`.
- Заполняет фронтматтер `title`, `description`, `date`, `tag`.
- При необходимости создаёт/редактирует категорию в `content/tags/<tag>.mdx`.
- Проверяет результат локально командой `pnpm dev`.

## 3. Требования к контенту

### 3.1 Главная (`content/index.mdx`)
- Фронтматтер содержит `type: posts` и `asIndexPage: true`.
- Позволяет вставлять React-компоненты (примерно как `BlogPage` в документации).
- Не дублирует заголовок `# …`; он генерируется из `metadata.title`.

### 3.2 Посты (`content/posts/*.mdx`)
Фронтматтер включает:
- `title` — название отчёта.
- `description` — краткое описание.
- `date` — ISO-формат (`YYYY-MM-DD` / `YYYY-MM-DDTHH:mm`).
- `tag` — категория (`history`, `culture`, `technology`, `analysis`, `people`).

### 3.3 Категории (`content/tags/*.mdx`)
- Фронтматтер: `title`, `description`, `tag`, `type: tag`.

## 4. Архитектура маршрутов

### 4.1 App Router
- `app/layout.tsx`
  - Подключает глобальные стили (`nextra-theme-blog/style.css`, `styles.css`).
  - Формирует шапку/футер по `theme.config.tsx`.
- `app/[[...slug]]/page.tsx`
  - Универсальный маршрут, использующий `importPage` и `generateStaticParamsFor` из `nextra/pages`.
  - Передаёт `metadata`, `toc` и т.п. в MDX-компоненты.

### 4.2 API
- `app/api/posts/route.ts`
  - Возвращает JSON со списком постов (slug, title, date, description, tag) для блока «Похожие материалы».

## 5. Компоненты

### 5.1 `mdx-components.tsx`
- Расширяет `useMDXComponents`, добавляя обёртку, которая вставляет `<RelatedPosts currentTag={metadata?.tag} />` в конце контента.

### 5.2 `components/RelatedPosts.tsx`
- Клиентский компонент (`"use client"`).
- Забирает данные через `/api/posts`, отфильтровывает по тэгу, исключает текущий slug, сортирует по дате, выводит до 5 элементов.

## 6. Конфигурация

- `next.config.mjs`
  ```js
  import nextra from 'nextra'

  const withNextra = nextra({
    defaultShowCopyCode: false,
    search: true
  })

  export default withNextra({
    reactStrictMode: true
  })
  ```
- `theme.config.tsx` — объект `siteConfig` c `logo`, `repository`, `nav`, `footer`, `search.placeholder`.
- `styles.css` — пользовательские правки (по умолчанию можно импортировать стиль темы).

## 7. Структура проекта

```
reports_blog/
├── app/
│   ├── layout.tsx
│   ├── [[...slug]]/page.tsx
│   └── api/posts/route.ts
├── content/
│   ├── index.mdx
│   ├── posts/*.mdx
│   └── tags/*.mdx
├── components/
│   └── RelatedPosts.tsx
├── mdx-components.tsx
├── theme.config.tsx
├── styles.css
├── package.json
├── tsconfig.json
└── README.md
```

## 8. Процесс добавления постов
1. Создать/обновить `content/posts/<slug>.mdx`.
2. Убедиться, что фронтматтер заполнен корректно (`title`, `description`, `date`, `tag`).
3. При необходимости обновить категории (`content/tags`) и навигацию в `theme.config.tsx`.
4. Запустить `pnpm dev`, проверить отображение и блок «Похожие материалы».

## 9. Команды разработки

```bash
pnpm install
pnpm dev
pnpm build
pnpm start
```

> Примечание: Next.js предупреждает о множественных lockfiles (находится `package-lock.json` в домашней директории). Чтобы убрать предупреждение — удалить лишний lockfile или задать `outputFileTracingRoot`.

## 10. Требования к окружению
- Node.js ≥ 18.
- pnpm 9.x.
- Доступ к npm registry.

## 11. Дополнительные замечания
- Контент полностью лежит в `content/`, никаких скриптов копирования не используется.
- Следить за тем, чтобы в MDX не было дублирующих заголовков (`# ...`).
- Предупреждения Nextra о Git timestamp не критичны; при желании можно отключить подсчёт или обеспечить git-историю.
