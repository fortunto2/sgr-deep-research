PRD: Zettelkasten-блог на Next.js + Nextra с public/private, индексами и git-версией
0) Коротко

Цель: git-first знания как Zettelkasten: атомарные заметки в Markdown/MDX, двунаправленные связи, индексы (MOC), публикация как сайта.

Права: публичные статьи видны всем; приватные и полный индекс доступны только автору (через Cloudflare Zero Trust).

Техстек: Next.js + Nextra (blog theme), pnpm, gray-matter; хранение контента в content/ (git).

Особенности: [[wikilink]] → универсальная ссылка /n/<slug>; обратные ссылки рендерятся снизу; два индекса (/ — public, /all — private).

Версии: история/диффы из git (API + страница History).

1) Область действия (Scope)

Писать заметки в .md|.mdx с frontmatter.

Разделять контент на public/private через status в frontmatter.

Автогенерация:

страниц /blog/<slug> (public) и /private/<slug> (private),

индексов (public-only JSON и full JSON),

карты обратных ссылок (public-safe и full).

Универсальная маршрутизация по [[slug]] через /n/<slug>.

Вики-функции: back-links; (опционально) History (git log/diff).

Вне области: сложный WYSIWYG-редактор, RBAC на уровне страниц (доверяем периметру Cloudflare).

2) Zettelkasten-подход: логика хранения
2.1 Атомарность и плоскость

1 заметка = 1 мысль.

Папки необязательны (ZK любит «плоско»), но допустимы. Навигация — через ссылки и структурные заметки (MOC).

2.2 Идентификаторы (slug)

Рекомендуемый формат файла:
YYYYMMDD-HHMMSS-title.md(x)
Примеры:
20250921-101530-atomic-idea.md
20250922-082000-graph-links.mdx

Уникальность, стабильность, удобная хронология.

2.3 Frontmatter (обязательно)
---
title: "Atomic idea about X"
description: "Коротко о сути"
date: 2025-09-21
tags: ["zk", "graphs"]
category: "knowledge"
status: public # или private (по умолчанию private)
aliases: ["atomic idea", "idea X"] # для переименований
---

2.4 Ссылки

Пишем в тексте: [[20250921-101530-atomic-idea]].

При сборке: [[wikilink]] → /n/20250921-101530-atomic-idea.

2.5 Обратные ссылки (back-links)

На sync-этапе строится граф from → to.

На странице заметки снизу рендерится список «на меня ссылаются».

Для публичных страниц показываем только связи между public-узлами.

2.6 Индексы (MOC / structure notes)

Это обычные заметки, где вручную собираются списки [[link]].

Можно держать MOC отдельно от заметок:

content/
  notes/    # атомарные
  indexes/  # MOC


Авто-индексы сайта:

/ — только public (SEO, «поделиться»),

/all — полный (закрыт Zero Trust).

3) Дерево проекта и артефакты
content/
  notes/
    20250921-101530-atomic-idea.md
    20250922-082000-graph-links.mdx
  indexes/
    moc-knowledge-graphs.md
  _assets/
    20250921-101530-atomic-idea/fig1.png
    20250922-082000-graph-links/schema.svg

pages/
  index.tsx              # public index
  all/index.tsx          # full index (закрыть ZT)
  n/[slug].tsx           # универсальный резолвер (закрыть ZT)
  api/private/...
  blog/                  # генерит sync (public)
  private/               # генерит sync (private)

components/
  Backlinks.tsx          # компонент обратных ссылок

public/                  # публичные JSON
  index-public.json
  backlinks-public.json
  slugs-public.json

.data/                   # приватные JSON (НЕ доступны из веба)
  index-all.json
  backlinks-all.json
  slugs-all.json

scripts/
  sync-content.mjs       # сборка контента/ссылок/индексов

4) Публикация и доступ

Public (status: public):

Страницы: /blog/<slug>,

Индекс: / → index-public.json,

Back-links: только public↔public из backlinks-public.json,

SEO: index,follow.

Private (всё, что не status: public):

Страницы: /private/<slug>,

Полный индекс: /all → /.data/index-all.json (SSR),

Back-links full: через закрытые API /api/private/...,

SEO: noindex,nofollow,

Доступ: Cloudflare Zero Trust закрывает:

/private/*

/all*

/n/*

/api/private/*

5) Поведение ссылок

Редактор пишет [[slug]] где угодно (в заметках, MOC).

Sync:

заменяет wikilinks на /n/<slug>;

строит forward/backward карты.

/n/<slug> (SSR, закрыт ZT) читает /.data/slugs-all.json и редиректит:

если slug → public → /blog/<slug>,

если private → /private/<slug>.

Благодаря этому можно свободно перемещать заметки по папкам, не ломая ссылки.

6) Индексы интерфейса

Публичный индекс /: читает index-public.json, список только public.

Полный индекс /all (ZT): читает /.data/index-all.json, показывает всё (с бейджем public|private).

MOC-заметки (ручные оглавления): обычные страницы, могут быть public или private.

7) Версии и история (wiki-слой)

Источник правды по версиям — git.

API: /api/wiki/history/[slug] → список коммитов, diff A↔B, содержимое на коммите.

UI: страница /blog/<slug>/history (public) и /private/<slug>/history (private).

Рекомендация: закрыть API history через Zero Trust либо отдавать историю только для public.

8) Build/Run (pnpm)

Скрипт scripts/sync-content.mjs запускается в predev и prebuild.
Он:

собирает все .md|.mdx из content/**,

парсит frontmatter,

превращает [[wikilink]] → /n/<slug>,

генерирует MDX-страницы в pages/blog и pages/private,

считает back-links (public-safe и full),

пишет JSON: public → public/…, private → .data/…,

добавляет <meta name="robots" noindex> на private.

Команды:

pnpm dev — локалка,

pnpm build && pnpm start — прод.

9) Безопасность и SEO

Приватные пути и API закрываются Cloudflare Zero Trust (SSO/почта/доступ по списку).

Публичные JSON не содержат приватных слагов/названий.

Приватные JSON хранятся вне /public (в /.data).

Private-страницы всегда отдают noindex,nofollow.

10) Миграции и переименования

Не меняй временную часть в имени (YYYYMMDD-HHMMSS), меняй только хвост -title.
Тогда slug остаётся стабильным.

Либо заполняй aliases в frontmatter и учи резолвер /n/[slug] читать алиасы из .data.

При массовых переименованиях запускай скрипт миграции ссылок (поиск/замена [[old]] → [[new]]), затем sync.

11) Пример заметки (public)
---
title: "Публичный пост"
description: "Описание"
date: 2025-09-10
tags: ["pub", "demo"]
status: public
---

Это публичный пост. Ссылка на приват: [[20250901-120000-private-note]].

12) Пример приватной заметки
---
title: "Приватная заметка"
date: 2025-09-01
tags: ["private", "zk"]
# status опущен → private по умолчанию
---

Приватный текст. Ссылка на публичный: [[20250910-090000-public-post]].

13) Acceptance Criteria

Заметка со status: public доступна по /blog/<slug>, видна в /, индексируема.

Заметка без status (private) доступна по /private/<slug> (только после ZT), не видна в /, видна в /all.

/n/<slug> корректно редиректит на /blog/<slug> или /private/<slug>; маршрут закрыт ZT.

На публичной странице back-links показывают только public→public.

Полный индекс /all показывает все (с бейджем статуса), закрыт ZT.

Приватные JSON не доступны напрямую из веба.

History API возвращает список коммитов для файла; diff A↔B и content@SHA работают.

14) Расширения (после MVP)

Поиск: Fuse.js (public/private раздельно).

Граф связей: d3/sigma (public-safe и private-full слои).

Авто-MOC по тегам/категориям (генерация страниц #graphs).

Алиасы/редиректы: словарь алиасов в .data и поддержка в /n/[slug].

CI-проверки: битые wikilinks, отсутствующие target-заметки, пустые title.

15) Почему так «по-ZK» и удобно в проде

Плоская структура и wikilinks снимают зависимость от каталогов; всё решают связи.

status в frontmatter даёт простой и явный механизм публикации.

Два слоя индексов (public/full) из коробки решают и SEO, и «рабочую» картину мира автора.

Git остаётся источником правды по версиям; UI-вью истории подключается без ломки пайплайна.