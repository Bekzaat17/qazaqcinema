// Поиск по каталогу: дебаунс ввода, гашение гонок и запись спроса.
//
// Отдельно от App: это механика, а не продукт — экран лишь показывает то, что хук уже
// разложил на «ищем / нашли / не нашли / не смогли спросить».

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type Movie } from "../lib/api";

// Пауза между вводом и запросом: набирающий человек не должен отправлять запрос на
// каждую букву.
const DEBOUNCE_MS = 300;

// Через сколько тишины в наборе считаем запрос ЗАКОНЧЕННЫМ и пишем его в спрос.
// Заметно больше дебаунса поиска — и в этом весь смысл: набирая «кунг фу панда»,
// человек по пути отправляет серверу «кун», «кунг ф», «кунг фу пан», и в статистику
// спроса такие огрызки попадать не должны — иначе очередь на озвучку («искали, но не
// нашли») состояла бы из недонабранных слов. Таймер сбрасывается на каждое изменение
// запроса, поэтому доживает до конца только та строка, на которой человек реально
// остановился.
const TRACK_MS = 1_200;

// Короче этого не ищем: на одной букве ответ бессмыслен, а запросов — на каждый ввод.
const MIN_QUERY_LEN = 2;

export interface Search {
  query: string;
  setQuery: (q: string) => void;
  /** Найденное; `null` — поиск не запускался либо сорвался (см. `failed`). */
  results: Movie[] | null;
  searching: boolean;
  /** Спросить не удалось. Отдельно от `results === []`: «не нашлось» и «не смог
   *  спросить» — разные ответы юзеру. */
  failed: boolean;
  /** Повторить тот же запрос (кнопка «Қайталау» на сбое). */
  retry: () => void;
}

export function useSearch(): Search {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Movie[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [failed, setFailed] = useState(false);

  // Гонки гасим монотонным reqId: ответ на устаревший запрос игнорируем.
  const reqId = useRef(0);
  // Счётчик ручных повторов: запрос тот же, а эффект перезапустить надо. Через deps —
  // а не вызовом функции поиска напрямую, чтобы повтор шёл ровно тем же путём, что и
  // обычный ввод.
  const [nonce, setNonce] = useState(0);
  const retry = useCallback(() => {
    setFailed(false);
    setNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < MIN_QUERY_LEN) {
      setResults(null);
      setFailed(false);
      setSearching(false);
      return;
    }
    setSearching(true);
    const id = ++reqId.current;
    const timer = setTimeout(() => {
      api
        .searchMovies(q)
        .then((res) => {
          if (id !== reqId.current) return;
          setFailed(false);
          setResults(res);
        })
        .catch(() => {
          // ⚠️ НЕ `setResults([])`: пустой массив рисует «Ештеңе табылмады», то есть
          // приложение уверенно сообщало бы «такого фильма у нас нет» на обычном обрыве
          // связи. Для человека, пришедшего за конкретным названием, это дезинформация —
          // он уйдёт, решив, что фильма нет. Ошибку показываем ошибкой.
          if (id !== reqId.current) return;
          setFailed(true);
          setResults(null);
        })
        .finally(() => {
          if (id === reqId.current) setSearching(false);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, nonce]);

  // Спрос словами: пишем запрос и сколько по нему нашлось. Отдельным эффектом от самого
  // поиска, с собственной, более длинной паузой (TRACK_MS) — сервер по своим запросам не
  // может отличить законченный запрос от префикса недонабранного слова. Ноль результатов
  // здесь — самая ценная строка: человек назвал, за чем пришёл, и ушёл ни с чем, а из
  // таких запросов и собирается очередь на озвучку.
  useEffect(() => {
    const q = query.trim();
    if (q.length < MIN_QUERY_LEN || results === null) return;
    const found = results.length;
    const timer = setTimeout(() => {
      // Фоном и молча: аналитика спроса не имеет права ни задержать выдачу результатов,
      // ни всплыть ошибкой перед человеком (тот же принцип, что у trackPaywall).
      void api.trackSearch(q, found).catch(() => {});
    }, TRACK_MS);
    return () => clearTimeout(timer);
  }, [query, results]);

  return { query, setQuery, results, searching, failed, retry };
}
