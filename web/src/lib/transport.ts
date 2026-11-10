/** Общий транспорт: ограничивает зависший запрос и сохраняет отмену вызывающего экрана. */
export class FetchTimeoutError extends Error {
  constructor() {
    super("request timeout");
    this.name = "FetchTimeoutError";
  }
}

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const upstream = init.signal;
  if (upstream?.aborted) {
    throw upstream.reason ?? new DOMException("Request aborted", "AbortError");
  }
  const controller = new AbortController();
  const cancel = () => controller.abort(upstream?.reason);
  upstream?.addEventListener("abort", cancel, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (timedOut) throw new FetchTimeoutError();
    throw error;
  } finally {
    clearTimeout(timer);
    upstream?.removeEventListener("abort", cancel);
  }
}
