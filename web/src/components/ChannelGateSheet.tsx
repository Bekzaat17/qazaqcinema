// «Подпишитесь на канал» — то, что видит человек, решивший взять фильм на неделю, но на
// канал не подписанный.
//
// Это НЕ пэйволл и выглядеть как пэйволл не должно: до бесплатного фильма ему остался
// один шаг, и просить денег в этот момент — верный способ не получить ни подписки, ни
// оплаты. Поэтому здесь нет ни цен, ни тарифов — только канал и «Тексеру».
//
// Две кнопки, а не одна: Telegram не сообщает Mini App о подписке, узнать о ней можно
// только спросив сервер. Поэтому человек сам возвращается и жмёт «Тексеру» — и это же
// единственный способ дать ему мгновенный ответ вместо «подождите, обновится».

import { Megaphone, RefreshCw } from "lucide-react";

import type { Movie } from "../lib/api";
import { haptic, openTelegramLink } from "../lib/telegram";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface ChannelGateSheetProps {
  open: boolean;
  movie: Movie | null;
  /** @-имя канала без «@» (с бэка). Пусто — кнопку в канал не рисуем, вести некуда. */
  channelUsername: string;
  busy: boolean;
  onRetry: (movie: Movie) => void;
  onClose: () => void;
}

export default function ChannelGateSheet({
  open,
  movie,
  channelUsername,
  busy,
  onRetry,
  onClose,
}: ChannelGateSheetProps) {
  if (!open || !movie) return null;

  return (
    <Sheet open onClose={onClose} labelledBy="gate-title">
      <div className="px-5 pb-4 pt-1 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          <Megaphone size={30} className="text-brand" />
        </div>
        <h2 id="gate-title" className="text-xl font-extrabold tracking-tight text-text">
          Каналға жазылыңыз
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Арнаға жазылсаңыз, аптасына бір фильмді тегін таңдай аласыз. «{movie.title_kk}» —
          сіздің осы апталық таңдауыңыз болады.
        </p>

        <div className="mt-5">
          {channelUsername && (
            <Button
              onClick={() => {
                haptic.light();
                openTelegramLink(`https://t.me/${channelUsername}`);
              }}
            >
              <Megaphone size={18} />
              Арнаға өту
            </Button>
          )}
          <Button
            variant="surface"
            loading={busy}
            onClick={() => onRetry(movie)}
            className={channelUsername ? "mt-2" : ""}
          >
            <RefreshCw size={17} />
            Тексеру
          </Button>
          <Button variant="ghost" onClick={onClose} className="mt-1">
            Кейінірек
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
