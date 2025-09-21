1. В контенте

В frontmatter заметки/индекса добавляем поле domain:

---
title: "Финансовый отчёт"
status: public
domain: finance.example.com
---


status управляет публичность/приватность.

domain говорит «этот пост должен открываться только на finance.example.com».

если domain не указан → идёт на основной домен.

2. На стороне Next.js

Билд остаётся один.

В getServerSideProps или в _middleware.ts ты смотришь на req.headers.host → подсовываешь нужный индекс и фильтруешь только те страницы, чей domain совпадает с текущим host.

Например:

const host = req.headers.host;
const filteredDocs = allDocs.filter(d =>
  !d.domain || d.domain === host
);

3. Cloudflare Workers (Router)

Worker выступает прокси перед Next.js.

Простейший worker.js:

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);

    // Проксируем все запросы на бэкенд (Vercel / свой сервер)
    // Один билд Next.js, один origin
    return fetch(`https://my-main-app.example.com${url.pathname}${url.search}`, {
      headers: req.headers,
      method: req.method,
      body: req.body
    });
  }
}


А теперь ключевое — в Cloudflare Dashboard:

DNS: добавляешь нужные сабдомены (например, finance.example.com, blog.example.com) → A/CNAME на твой worker.

Workers Routes: указываешь finance.example.com/* и blog.example.com/*, оба идут на один и тот же worker.js.

Внутри приложения Next ты уже смотришь req.headers.host и решаешь, что показывать.

4. Как это будет выглядеть

На blog.example.com открываются только заметки с domain: blog.example.com или без поля domain.

На finance.example.com открываются только заметки с domain: finance.example.com.

Один билд Next.js, один код.

Cloudflare разруливает, какой хостнейм подать, а твой Next фильтрует контент.

5. Что нужно в Cloudflare

DNS-записи для каждого сабдомена/домена.

Worker с роутами для каждого сабдомена.

Опционально: Zero Trust policies для приватных частей (/private/*, /all/*).

Хочешь — я соберу пример _middleware.ts для Next, который будет фильтровать страницы по domain прямо на уровне запроса?

You said:
а список доменов динамично или надо в коднфиге держать?
ChatGPT said:

можно сделать так, чтобы список доменов был динамическим — прямо в frontmatter у заметок/индексов, без хардкода в next.config.js.

как это работает

В заметке пишешь:

---
title: "Финансовый отчёт"
status: public
domain: finance.example.com
---


sync-скрипт собирает все domain и группирует заметки. В JSON-индексах появляется поле domain.

Next.js:

на каждый запрос смотришь на req.headers.host;

показываешь только те заметки, у которых domain пустой (основной сайт) или совпадает с этим host.

const host = req.headers.host;
const filtered = allDocs.filter(
  d => !d.domain || d.domain === host
);


Cloudflare Workers:

один билд Next.js → один origin (например, mainapp.example.com).

в Cloudflare DNS добавляешь все сабдомены (blog.example.com, finance.example.com …).

в Workers Routes указываешь *.example.com/* → твой worker.

worker просто проксирует всё на origin, сохраняя Host:

export default {
  async fetch(req) {
    const url = new URL(req.url);
    return fetch(`https://mainapp.example.com${url.pathname}${url.search}`, {
      headers: req.headers, method: req.method, body: req.body
    });
  }
}


то есть никаких хардкод-списков в конфиге не нужно, Next сам фильтрует по host.

✅ Итог: список доменов живёт прямо в заметках → можно хоть каждый пост на свой сабдомен.
На Cloudflare — только добавить DNS-записи и роут на воркер, больше конфигов держать не нужно.

Хочешь, я распишу готовый паттерн для sync-content.mjs, чтобы он автоматически собирал список всех доменов из заметок и писал, какие посты к какому домену относятся?