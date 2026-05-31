# URL Shortener (React + Vite)

## Работу сайта можно протестировать по ссылке `https://nikita-2406.github.io/link_shortener/`

Локальное SPA-приложение для сокращения ссылок с хранением в `localStorage`.

## Возможности

- Сокращение длинного URL в короткий URL формата `http://localhost:5173/<shortCode>`.
- Повторное сокращение того же длинного URL возвращает существующую короткую ссылку.
- Разрешение короткой ссылки в длинную.
- Автоматический редирект при открытии короткой ссылки `/<shortCode>`.
- Подсчет количества переходов (`hitCount`) по короткой ссылке.
- Ограничение емкости хранилища (`capacity`), задается пользователем при старте.
- Политика вытеснения при переполнении: LFU + FIFO по времени создания:
  - удаляется запись с минимальным `hitCount`;
  - при равном `hitCount` удаляется более старая (`createdAt` меньше).

## Технологии

- React 19
- Vite 8
- ESLint
- `localStorage` браузера для персистентности

## Архитектура (OOP)

Основная логика отделена от UI.

- `UrlEntry` (`src/lib/urlStore.js`)
  - доменная сущность ссылки (`id`, `longUrl`, `shortCode`, `hitCount`, `createdAt`);
  - методы `incrementHits()`, `toJSON()`, `fromJSON()`.
- `UrlRepository` (`src/lib/urlStore.js`)
  - слой доступа к `localStorage`;
  - методы `load()` и `save()`.
- `UrlShortenerService` (`src/lib/urlStore.js`)
  - бизнес-логика: `init()`, `shorten()`, `resolve()`, `listAll()`, `persist()`;
  - управление индексами и вытеснением.
- `App` (`src/App.jsx`)
  - UI, формы и отображение данных;
  - вызывает только публичные методы сервиса.

## Структура данных

Каждая запись:

```json
{
  "id": "string",
  "longUrl": "string",
  "shortCode": "string",
  "hitCount": 0,
  "createdAt": 1710000000000
}
```

Состояние хранится в `localStorage` под ключом `link_shortener_store_v1`.

## Индексы и оптимизация

Для ускорения операций используются два `Map`:

- `longToShort: Map<longUrl, shortCode>`
- `shortToEntry: Map<shortCode, UrlEntry>`

Это позволяет избежать полного сканирования коллекции в основных горячих сценариях.

## Сложность алгоритмов

- Инициализация из `localStorage` + построение индексов: **O(n)** по времени, **O(n)** по памяти.
- `shorten(longUrl)`:
  - проверка дубля по `longToShort`: **O(1)** в среднем;
  - генерация уникального short code: **O(1)** в среднем (пока коллизии редки);
  - при переполнении вытеснение LFU+FIFO: **O(n)** (линейный поиск кандидата);
  - вставка и обновление индексов: **O(1)** в среднем.
- `resolve(shortCode)`:
  - поиск по `shortToEntry`: **O(1)** в среднем;
  - инкремент счетчика и сохранение: доменная операция **O(1)** + сериализация состояния **O(n)**.
- `listAll()`:
  - копирование + сортировка по `createdAt`: **O(n log n)**.

Примечание: из-за полного сохранения снимка состояния в `localStorage` после изменений есть дополнительная стоимость сериализации `O(n)`.

## Поведение редиректа

При старте приложения анализируется `window.location.pathname`:

- если путь пустой (`/`) — открывается стандартный UI;
- если путь содержит `shortCode` — выполняется `resolve(shortCode)` и `window.location.replace(longUrl)`;
- если код не найден — редирект не выполняется, UI продолжает работу.

## Валидация и ограничения

- Поддерживаются только `http` и `https` URL.
- `capacity` должна быть целым числом > 0.
- При битых данных в `localStorage` используется безопасный fallback на пустое состояние.

## Запуск проекта

```bash
yarn install
yarn dev
```

Приложение будет доступно по адресу из Vite (обычно `http://localhost:5173`).

## Docker

Из корня React-проекта:

```bash
cd "JS+React/link shortner"
```

**Production (Nginx, порт 8080):**

```bash
docker compose up --build web
```

Откройте http://localhost:8080

**Development (Vite с hot-reload, порт 5173):**

```bash
docker compose --profile dev up --build dev
```

Откройте http://localhost:5173

Для сборки с другим `base` (например, GitHub Pages):

```bash
VITE_BASE_PATH=/link_shortener/ docker compose build web
```

## Проверка качества

```bash
yarn lint
yarn build
```
