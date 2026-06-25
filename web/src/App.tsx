export default function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <img
        src="/logo.png"
        alt="QazaqCinema"
        className="w-44 max-w-[60%] drop-shadow-[0_0_40px_rgba(56,138,255,0.35)]"
      />
      <p className="max-w-sm text-neutral-400">
        Қазақша дубляжбен сирек мультфильмдер мен аниме.
      </p>
      <p className="max-w-sm text-sm text-neutral-600">
        Web App каркасы дайын. Интерфейс (каталог, пэйволл, іздеу, модалкалар) — PLAN.md «фронтенд»
        фазасы бойынша келесі сессияларда.
      </p>
    </main>
  );
}
