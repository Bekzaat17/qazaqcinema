import { ArrowRight, Check, LockKeyhole, Mountain, Sparkles, TreePine } from "../../ui-kit/adapters/icons";
import { dailyTasks, LESSON_REWARD } from "../resources";
import { SHRINES, type Progress, type WorldTarget } from "../types";

export default function ResourceJournal({ progress, busy, onStart }: {
  progress: Progress;
  busy: boolean;
  onStart: (target: WorldTarget) => void;
}) {
  const tasks = dailyTasks(progress, SHRINES);
  const remaining = tasks.filter((task) => !task.done).length;
  return <div className="quest-journal">
    <div className="quest-journal-hero">
      <span className="quest-journal-kicker"><Sparkles size={16} /> КҮНДЕЛІКТІ МАРАПАТ</span>
      <h3>Білім жина. Ауылыңды өсір.</h3>
      <p>3 сұраққа жауап бер — құрылысқа материал ал.</p>
      <div className="quest-journal-yield">
        <span><TreePine size={22} /><b>+{LESSON_REWARD.wood}</b> ағаш</span>
        <span><Mountain size={22} /><b>+{LESSON_REWARD.stone}</b> тас</span>
        <span><Sparkles size={22} /><b>≤{LESSON_REWARD.maxXp}</b> XP</span>
      </div>
      <small lang="ru">За каждое задание из 3 вопросов: 25 дерева и 15 камня. Награда начисляется автоматически после последнего ответа.</small>
    </div>
    <div className="quest-journal-heading"><b>Бүгінгі тапсырмалар</b><span>{progress.completed_today.length} / 3 аяқталды</span></div>
    <div className="quest-task-list">
      {tasks.map(({ target, done, locked, prerequisite }, index) => <button
        key={target.id}
        className={`quest-task ${done ? "is-done" : ""}`}
        disabled={busy || done || locked}
        onClick={() => onStart(target)}
      >
        <span className={`quest-task-art spirit-${target.id}`}>{done ? <Check size={23} /> : locked ? <LockKeyhole size={22} /> : <span>{index + 1}</span>}</span>
        <span className="quest-task-copy"><b>{target.name}</b><small>{done ? "Марапат алынды · ертең қайта кел" : locked ? `Алдымен «${prerequisite}» тапсырмасын аяқта` : "3 сұрақ · +25 ағаш · +15 тас"}</small></span>
        {!done && !locked && <ArrowRight size={19} />}
      </button>)}
    </div>
    <div className="quest-journal-note">
      <b>{remaining ? `Бүгін тағы ${remaining * LESSON_REWARD.wood} ағаш пен ${remaining * LESSON_REWARD.stone} тас жинай аласың` : "Бүгінгі барлық марапат алынды ✓"}</b>
      <p lang="ru">{remaining ? "Нажми на доступное задание выше. Искать духа на карте не обязательно. Ошибся? Попробуй ещё раз — дерево и камень всё равно получишь." : "Новые задания и награды появятся в 00:00 по времени Алматы. Повторное открытие задания не даёт ресурсы снова."}</p>
    </div>
    <div className="quest-resource-explainer" lang="ru"><TreePine size={18} /><p><b>Дерево и камень — для строительства.</b> XP — опыт для уровня и рейтинга. Отдельных монет в ауыле нет; здания не производят ресурсы.</p></div>
  </div>;
}
