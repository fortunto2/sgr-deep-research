# Тестовая заметка

Это тестовая заметка для проверки функциональности системы.

## Код

```javascript
const fetchContent = async (slug) => {
  const response = await fetch(`https://pub-33dec9645c443eef5859b1e10ce71e01.r2.dev/${slug}.md`);
  return response.text();
};
```

## Список

- Пункт 1
- Пункт 2
- Пункт 3

## Ссылки

- [[welcome]] - Главная заметка
- [[about]] - О проекте

> Это цитата для демонстрации возможностей markdown.