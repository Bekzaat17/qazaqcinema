// Обратный отсчёт до момента (ISO-строка с сервера) в казахской формулировке.
//
// Срок приходит с бэкенда (`hero_free_until` — ближайшая местная полночь), а не считается
// здесь: правило суток живёт в домене (`domain/catalog/daily`), и отсчёт на экране обязан
// сходиться с тем, что реально пустит выдача видео. Тут только формат.
//
// Тикаем раз в 30 с: точность — минуты, а каждую секунду перерисовывать hero незачем
// (лишние рендеры на слабом телефоне заметнее, чем «минута дрогнула на полминуты позже»).

import { useEffect, useState } from "react";

const TICK_MS = 30_000;

/** «14 сағ 32 мин» / «47 мин». Ноль и прошедшее время → null (подписи не будет). */
function format(msLeft: number): string | null {
  if (msLeft <= 0) return null;
  const minutes = Math.ceil(msLeft / 60_000);
  const hours = Math.floor(minutes / 60);
  // Меньше минуты уже округлилось вверх до 1 — «0 мин» не покажем никогда.
  return hours > 0 ? `${hours} сағ ${minutes % 60} мин` : `${minutes} мин`;
}

export function useCountdown(until: string | null): string | null {
  const [left, setLeft] = useState<string | null>(() =>
    until ? format(Date.parse(until) - Date.now()) : null,
  );

  useEffect(() => {
    if (!until) {
      setLeft(null);
      return;
    }
    const deadline = Date.parse(until);
    if (Number.isNaN(deadline)) {
      setLeft(null); // битая дата — молча без таймера, hero всё равно рабочий
      return;
    }
    const tick = () => setLeft(format(deadline - Date.now()));
    tick();
    const timer = setInterval(tick, TICK_MS);
    return () => clearInterval(timer);
  }, [until]);

  return left;
}
