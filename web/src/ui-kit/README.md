# Qazaq UI kit

Слой адаптеров для QazaqCinema и QazaqMusic. Живые примеры: `/ui-kit`.

Экраны импортируют `Button`, `Card`, `Badge`, `Progress`, `Dialog`, `Brand` из `ui-kit`.
Иконки импортируются из `ui-kit/adapters/icons`. Внешние библиотеки подключаются только
в `adapters/`; их типы и классы не становятся частью публичного API.

```tsx
import { Button, Card, Progress } from "../ui-kit";
import { Film } from "../ui-kit/adapters/icons";

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
| Старый вход кинотеатра | реэкспорт общего Button | `../ui/Button.tsx` |

Другой UI-набор подключается внутри адаптера с отображением наших вариантов,
состояний и событий в его API. Новую библиотеку не нужно распространять по экранам.

`tokens.css` задаёт бренд, типографику, радиусы, интервалы и анимацию. Кинотеатр использует
тёмные поверхности и синие основные действия. Не подменять фирменные цвета платёжных сервисов.

`Brand` использует основной знак `/logo-icon.png`: product задаёт вордмарк,
subtitle — подпись режима, compact — размер для шапки.
