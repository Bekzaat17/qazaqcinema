import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, Film, Popcorn } from "./adapters/icons";
import { Badge, Brand, Button, Card, Dialog, Progress } from "./index";
import "./showcase.css";

function ThemeSample() {
  const [dialog, setDialog] = useState(false);
  const [watched, setWatched] = useState(3);
  return <section className="kit-theme" data-ui-theme="cinema">
    <Brand product="cinema" subtitle="Қазақша кинотеатр" />
    <div className="kit-theme-heading"><span className="ui-eyebrow">01 / CINEMA</span>
      <h2>Кино кеші</h2><p>Бір әлем. Бір қолтаңба.</p></div>
    <div className="kit-row"><Badge tone="brand">Qazaq әлемі</Badge><Badge tone="success"><Check size={12} /> Сақталған</Badge><Badge tone="gold">8.4</Badge></div>
    <Card>
      <span className="kit-card-icon"><Popcorn size={30} strokeWidth={1.5} /></span>
      <h3>Қазақша дубляж</h3><p>Сирек мультфильмдер мен аниме бір жерде.</p>
      <div className="kit-resource"><span><Film size={16} /> {watched} фильм</span><span>{watched} / 9</span></div>
      <Progress value={watched} max={9} label="Көрілгені" />
      <Button onClick={() => setWatched((value) => value >= 9 ? 0 : value + 1)}>
        <Film size={18} /> Көру <ArrowRight size={16} />
      </Button>
    </Card>
    <div className="kit-actions"><Button block={false} onClick={() => setDialog(true)}>Терезені ашу</Button>
      <Button variant="secondary" block={false}>Екінші</Button>
      <Button variant="ghost" block={false}>Кейінірек</Button></div>
    <div className="kit-actions"><Button size="sm" block={false}>Шағын</Button><Button disabled block={false}>Қолжетімсіз</Button><Button loading block={false}>Жүктелуде</Button></div>
    {dialog && <Dialog title="Фильм чатқа жіберілді" eyebrow="QAZAQ ӘЛЕМІ" theme="cinema" onClose={() => setDialog(false)}>
      <p>Видео бот чатында сізді күтіп тұр.</p>
      <Button onClick={() => setDialog(false)}>Түсінікті <Check size={17} /></Button>
    </Dialog>}
  </section>;
}

export default function Showcase() {
  return <main className="kit-showcase">
    <header><a href="/"><ArrowLeft size={16} /> Кинотеатрға оралу</a><span>QAZAQ / DESIGN SYSTEM</span></header>
    <div className="kit-intro"><Badge tone="brand">UI KIT · 01</Badge><h1>Бір әлемнің<br /><em>ортақ тілі.</em></h1>
      <div className="kit-brand-pair"><Brand product="cinema" mark={false} compact /></div></div>
    <div className="kit-palette">{["#3d8bff", "#edc979", "#34d399", "#09090b"].map((color) =>
      <div key={color}><i style={{ background: color }} /><span>{color}</span></div>)}</div>
    <div className="kit-themes"><ThemeSample /></div>
  </main>;
}
