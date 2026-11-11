import { useEffect, useState } from "react";
import { History, Trophy } from "../../ui-kit/adapters/icons";
import { BOT_URL, openTelegramLink } from "../../lib/telegram";
import type { GameGateway } from "../gateway";
import type { Catalog, GameHistory, GameRanking } from "../types";
import { money } from "../format";

export default function GameRecords({ gateway, catalog, mode }:
  { gateway: GameGateway; catalog: Catalog; mode: "history" | "ranking" }) {
  const [history, setHistory] = useState<GameHistory[]>([]), [ranking, setRanking] = useState<GameRanking | null>(null);
  const [loading, setLoading] = useState(true), [error, setError] = useState(false);
  const [retry, setRetry] = useState(0), [offset, setOffset] = useState(0), [more, setMore] = useState(false);
  useEffect(() => {
    let active = true;
    if (gateway.practice) return;
    setLoading(true); setError(false);
    const request = mode === "history" ? gateway.history(offset).then((items) => {
      if (active) { setHistory((old) => offset ? [...old, ...items] : items); setMore(items.length === 20); }
    }) : gateway.ranking().then((data) => { if (active) setRanking(data); });
    void request.catch(() => { if (active) setError(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [gateway, mode, retry, offset]);
  if (gateway.practice) return <div className="dala-room-empty"><Trophy size={32} /><h3>Жаттығу рейтингке кірмейді</h3><p>Жеке тарих пен жеңістер рейтингі Telegram-дағы аяқталған ортақ партиялардан құралады.</p><button className="dala-primary" onClick={() => openTelegramLink(`${BOT_URL}?startapp=quest`)}>Telegram-да ойнау</button></div>;
  return <div className="dala-game-records">
    <p className="dala-muted">{mode === "history" ? "Аяқталған әр партияның нәтижесі серверде сақталады." : "Жеңістер саны бойынша. Тең болса, жеңіс пайызы, одан кейін тұрақты орын реті қолданылады."}</p>
    {loading && <p role="status">Жүктелуде…</p>}
    {error && <div role="alert"><p>Деректер жүктелмеді.</p><button className="dala-secondary" onClick={() => setRetry((n) => n + 1)}>Қайта көру</button></div>}
    {mode === "history" ? <>
      {!loading && !error && !history.length && <div className="dala-room-empty"><History size={32} /><h3>Әзірге аяқталған партия жоқ</h3><p>Бірінші ортақ ойыныңды аяқтаған соң нәтиже осында көрінеді.</p></div>}
      {history.map((game) => <article className="dala-game-history" key={game.code}>
        <div><b>{catalog.boards.find((b) => b.id === game.board_id)?.name ?? game.board_id}</b><span className={game.won ? "is-win" : ""}>{game.won ? "Жеңіс" : "Аяқталды"}</span></div>
        <p>{new Date(game.finished_at).toLocaleString("kk-KZ", { dateStyle: "medium", timeStyle: "short" })} · {game.rounds} айналым · {game.player_count} ойыншы</p>
        <small>Жеңімпаз: {game.winner_name} · Сенің капиталың: {money(game.capital)}</small>
      </article>)}
      {more && <button className="dala-secondary dala-full" disabled={loading} onClick={() => setOffset(history.length)}>Тағы көрсету</button>}
    </> : <>
      {!loading && !error && !ranking?.entries.length && <div className="dala-room-empty"><Trophy size={32} /><h3>Рейтинг алғашқы партиялардан басталады</h3></div>}
      {ranking?.me && <p className="dala-my-rank">Сенің орның: <b>#{ranking.me.rank}</b> · {ranking.me.wins} жеңіс / {ranking.me.played} партия</p>}
      <ol className="dala-standings">{ranking?.entries.map((entry) => <li key={entry.rank} className={entry.is_me ? "is-me" : ""}><b>{entry.rank}</b><div><strong>{entry.name}{entry.is_me ? " · Сен" : ""}</strong><small>{entry.played} партия · {Math.round(entry.wins / entry.played * 100)}% жеңіс</small></div><span>{entry.wins} жеңіс</span></li>)}</ol>
    </>}
  </div>;
}
