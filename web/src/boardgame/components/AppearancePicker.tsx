import PlayerAvatar, { type PlayerAppearance, type Portrait } from "../../ui-kit/PlayerAvatar";

export default function AppearancePicker({ appearance, onChange }:
  { appearance: PlayerAppearance; onChange: (value: Portrait) => void }) {
  return <div className="dala-appearance-picker">
    <span>Ойындағы бейнең</span>
    {appearance.avatar_url && <div className="dala-telegram-avatar">
      <PlayerAvatar appearance={appearance} size={42} /><span>Telegram суретің<small>Профильдегідей көрсетіледі</small></span>
    </div>}
    <div className="dala-portrait-options" role="group" aria-label="Сурет болмағандағы кейіпкер">
      {(["male", "female"] as const).map((portrait) => <button key={portrait} type="button"
        aria-pressed={appearance.portrait === portrait} onClick={() => onChange(portrait)}>
        <PlayerAvatar appearance={{ portrait }} size={34} />{portrait === "male" ? "Ер кейіпкер" : "Әйел кейіпкер"}
      </button>)}
    </div>
    <small>{appearance.avatar_url ? "Фото ашылмаса, таңдаған кейіпкерің көрінеді." : "Telegram суреті болмаса, осы кейіпкер көрінеді."}</small>
  </div>;
}
