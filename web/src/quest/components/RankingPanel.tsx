import { useEffect, useState } from "react";
import { Trophy } from "lucide-react";
import { BOT_URL, openTelegramLink } from "../../lib/telegram";
import type { Period, QuestGateway, Ranking } from "../types";

export default function RankingPanel({ gateway }: { gateway: QuestGateway }) {
  const [period, setPeriod] = useState<Period>("week");
  const [data, setData] = useState<Ranking | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError(false);
    gateway
      .ranking(period)
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [gateway, period, retry]);
  if (gateway.practice)
    return (
      <div className="quest-empty">
        <Trophy size={42} />
        <h3>Нағыз саяхат осында басталады</h3>
        <p>
          Жаттығу ұпайлары рейтингке кірмейді. Өз ауылыңды сақтап, жарысу үшін
          Telegram арқылы кір.
        </p>
        <button
          className="quest-primary"
          onClick={() => openTelegramLink(`${BOT_URL}?startapp=quest`)}
        >
          Telegram-да ойнау ↗
        </button>
      </div>
    );
  return (
    <>
      <div className="quest-tabs">
        <button
          aria-pressed={period === "week"}
          onClick={() => setPeriod("week")}
        >
          Осы апта
        </button>
        <button
          aria-pressed={period === "all"}
          onClick={() => setPeriod("all")}
        >
          Барлық уақыт
        </button>
      </div>
      <p className="quest-muted">
        Топ-10 әр 5 минут сайын жаңарады. Сенің орның — ағымдағы нәтиже.
      </p>
      {error ? (
        <div className="quest-empty">
          <p>Рейтинг жүктелмеді.</p>
          <button
            className="quest-secondary"
            onClick={() => setRetry((v) => v + 1)}
          >
            Қайталау
          </button>
        </div>
      ) : !data ? (
        <p role="status">Рейтинг жүктелуде…</p>
      ) : (
        <>
          <ol className="quest-ranking">
            {data.leaders.map((row) => (
              <li key={row.rank} className={row.is_self ? "is-self" : ""}>
                <span className="quest-rank-number">
                  {row.rank <= 3 ? ["🥇", "🥈", "🥉"][row.rank - 1] : row.rank}
                </span>
                <span>
                  {row.name}
                  {row.is_self && <small>Бұл сен</small>}
                </span>
                <strong>
                  {row.points}
                  <small>ұпай</small>
                </strong>
              </li>
            ))}
          </ol>
          {!data.leaders.length && (
            <p className="quest-empty">Алғашқы рухты оятып, рейтингті баста!</p>
          )}
          {data.me && (
            <div className="quest-my-rank">
              <span>
                Сенің орның <b>#{data.me.rank}</b>
              </span>
              <b>{data.me.points} ұпай</b>
            </div>
          )}
          <p className="quest-muted">
            Рейтингте ойын псевдонимің көрсетіледі. Ұпай тең болса, тұрақты
            ойыншы реті қолданылады. Апта дүйсенбі 00:00-де, Алматы уақытымен
            басталады.
          </p>
        </>
      )}
    </>
  );
}
