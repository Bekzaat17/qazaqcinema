import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, Dices, TentTree, TreePine } from "./adapters/icons";
import { Badge, Brand, Button, Card, Dialog, Progress } from "./index";
import "./showcase.css";

function ThemeSample({ theme }: { theme: "cinema" | "steppe" }) {
  const [dialog, setDialog] = useState(false);
  const [development, setDevelopment] = useState(3);
  return <section className="kit-theme" data-ui-theme={theme}>
    <Brand product={theme === "cinema" ? "cinema" : "play"} subtitle={theme === "cinema" ? "Қазақша кинотеатр" : "Ойындар әлемі"} />
    <div className="kit-theme-heading"><span className="ui-eyebrow">{theme === "cinema" ? "01 / CINEMA" : "02 / STEPPE"}</span>
      <h2>{theme === "cinema" ? "Кино кеші" : "Менің ауылым"}</h2><p>Бір әлем. Бір қолтаңба.</p></div>
    <div className="kit-row"><Badge tone="brand">Qazaq әлемі</Badge><Badge tone="success"><Check size={12} /> Сақталған</Badge><Badge tone="gold">150 XP</Badge></div>
    <Card>
      <span className="kit-card-icon"><TentTree size={30} strokeWidth={1.5} /></span>
      <h3>Өз ауылың. Өз хикаяң.</h3><p>Зертте, үйрен және арманыңдағы ауылды құр.</p>
      <div className="kit-resource"><span><TreePine size={16} /> 75 ағаш</span><span>{development} / 9 даму</span></div>
      <Progress value={development} max={9} label="Ауылдың дамуы" />
      <Button onClick={() => setDevelopment((value) => value >= 9 ? 0 : value + 1)}>
        <TentTree size={18} /> Ауылды дамыту <ArrowRight size={16} />
      </Button>
    </Card>
    <div className="kit-actions"><Button block={false} onClick={() => setDialog(true)}>Терезені ашу</Button>
      <Button variant="secondary" block={false}><Dices size={17} /> Үстел ойыны</Button>
      <Button variant="ghost" block={false}>Кейінірек</Button></div>
    <div className="kit-actions"><Button size="sm" block={false}>Шағын</Button><Button disabled block={false}>Қолжетімсіз</Button><Button loading block={false}>Жүктелуде</Button></div>
    {dialog && <Dialog title="Ауылың гүлденіп келеді" eyebrow="QAZAQ ӘЛЕМІ" theme={theme} onClose={() => setDialog(false)}>
      <p>Рухтардың тапсырмаларын орындап, жаңа ғимараттар сал.</p>
      <Button onClick={() => setDialog(false)}>Түсінікті <Check size={17} /></Button>
    </Dialog>}
  </section>;
}

export default function Showcase() {
  return <main className="kit-showcase">
    <header><a href="/quest"><ArrowLeft size={16} /> Ойынға оралу</a><span>QAZAQ / DESIGN SYSTEM</span></header>
    <div className="kit-intro"><Badge tone="brand">UI KIT · 01</Badge><h1>Бір әлемнің<br /><em>ортақ тілі.</em></h1>
      <div className="kit-brand-pair"><Brand product="cinema" mark={false} compact /><Brand mark={false} compact /></div></div>
    <div className="kit-palette">{["#3d8bff", "#edc979", "#34d399", "#09090b", "#fbf8ed"].map((color) =>
      <div key={color}><i style={{ background: color }} /><span>{color}</span></div>)}</div>
    <div className="kit-themes"><ThemeSample theme="cinema" /><ThemeSample theme="steppe" /></div>
  </main>;
}
