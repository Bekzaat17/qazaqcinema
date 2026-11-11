# Qazaq UI kit

Слой адаптеров для QazaqCinema, «Дала дәулеті» и аула. Живые примеры: `/ui-kit`.

Экраны импортируют `Button`, `Card`, `Badge`, `Progress`, `Dialog`, `Brand` из `ui-kit`.
Иконки импортируются из `ui-kit/adapters/icons`. Внешние библиотеки подключаются только
в `adapters/`; их типы и классы не становятся частью публичного API.

```tsx
import { Button, Card, Progress } from "../ui-kit";
import { TentTree } from "../ui-kit/adapters/icons";

<Card>
  <Progress value={3} max={9} label="Ауылдың дамуы" />
  <Button variant="primary" loading={false} onClick={build}>
    <TentTree size={18} /> Ауылды дамыту
  </Button>
</Card>
```

- `Button`: primary / secondary / surface / ghost / danger / kaspi / stars;
  size sm / md / lg; block, loading, HTML-атрибуты. По умолчанию type=button.
- `Card`: поверхность с HTML-атрибутами, отступами и рамкой.
- `Badge`: neutral / brand / gold / success.
- `Progress`: ограничивает значение диапазоном 0..max, сообщает значение скринридеру.
- `Dialog`: нативный modal dialog, удержание фокуса, Esc через onClose,
  title, eyebrow, theme. Кнопкой Telegram управляет экран.

## Поставщики

| Слой | Реализация | Где заменить |
| --- | --- | --- |
| Базовые компоненты | React + HTML / CSS | `adapters/react.tsx` |
| Модальные окна | HTMLDialogElement | `adapters/Dialog.tsx` |
| Иконки | Lucide | `adapters/icons.ts` |
| Игровые классы | CSS bridge | `adapters/games.css` |
| Старый вход кинотеатра | реэкспорт общего Button | `../ui/Button.tsx` |
| 3D-объекты | Three.js + Quaternius / Kenney GLB | `../graphics/models.ts` |

Другой UI-набор подключается внутри адаптера с отображением наших вариантов,
состояний и событий в его API. Новую библиотеку не нужно распространять по экранам.

`tokens.css` задаёт бренд, типографику, радиусы, интервалы и анимацию. Кинотеатр использует
тёмные поверхности и синие основные действия, игра — светлую тему `steppe`.
В игре основные действия золотые, покупка зелёная, продажа красная. Для независимого светлого блока использовать
`data-ui-theme="steppe"`. Не подменять фирменные цвета платёжных сервисов.

## 3D-адаптер

`ModelLibrary.batch(id, placements)` принимает игровые ID, координаты, высоту и поворот.
Он выравнивает модель по центру основания, приводит к заданной высоте и использует
InstancedMesh для повторений. Масштабы исходных коллекций не попадают в игровой код.
Ресурсы освобождаются через `dispose()`, включая завершившиеся после ухода загрузки.
Деревья имеют геометрический fallback при ошибке загрузки.

Исходники, лицензия CC0 и SHA-256: `public/models/*/sources.json`.
Модели обслуживаются локально; во время игры обращений к поставщикам нет.

`Brand` использует основной знак `/logo-icon.png`: product=cinema/play задаёт вордмарк,
subtitle — подпись режима, compact — размер для шапки кинотеатра.

Игровые значки `GameCoin`, `YurtIcon`, `WellIcon` — собственные SVG-компоненты.
Монета Dala обозначается `◈` в компактных ценах и золотым GameCoin в балансе.
Публичный формат валюты и преобразование старых журналов: `boardgame/format.ts`.

`PlayerAvatar` — общий SVG-портрет для UI и фишек поля. Принимает avatar_url / portrait
(male, female), цвет места и размер. Фото обрезается кругом, ошибка загрузки открывает
запасной портрет. В игре URL проверяется через `boardgame/appearance.ts` и серверный DTO.
