// Последняя сеть безопасности UI.
//
// Без неё любое исключение в рендере размонтирует всё дерево React, и человек остаётся с
// ПУСТЫМ чёрным экраном — без текста, без кнопки, без единого намёка на то, что делать.
// Это худший из возможных тупиков: приложение выглядит сломанным насмерть, хотя лечится
// перезагрузкой.
//
// Ловит именно то, чего не поймает ни один try/catch в обработчиках: неожиданную форму
// данных с бэкенда. Пример из реальной жизни этого проекта — фронт новой версии против
// бэкенда старой: у фильма нет поля `categories`, и `movie.categories.map` бросает
// TypeError прямо в рендере карточки.
//
// Классовый компонент — не стиль, а необходимость: `componentDidCatch`/
// `getDerivedStateFromError` в хуках не существуют.

import { RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  failed: boolean;
}

export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // В консоль клиента Telegram — единственная диагностика, доступная нам постфактум:
    // юзер сможет прислать скриншот, а мы поймём, что упало.
    console.error("Ошибка рендера:", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="flex min-h-screen flex-col items-center justify-center px-8 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface text-faint">
          <RotateCcw size={28} />
        </div>
        <p className="text-lg font-semibold text-text">Бір нәрсе дұрыс болмады</p>
        <p className="mt-1.5 max-w-xs text-sm text-muted">
          Қосымшаны қайта жүктеп көріңіз — деректеріңіз сақталады.
        </p>
        <button
          type="button"
          // Перезагрузка, а не сброс состояния: мы не знаем, что именно упало, и
          // повторный рендер того же битого состояния упал бы снова.
          onClick={() => window.location.reload()}
          className="mt-5 inline-flex w-full max-w-[220px] items-center justify-center rounded-2xl bg-brand px-5 py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition-transform duration-150 active:scale-[0.98]"
        >
          Қайта жүктеу
        </button>
      </div>
    );
  }
}
