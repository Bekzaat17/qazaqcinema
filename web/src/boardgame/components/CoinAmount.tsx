import { GameCoin } from "../../ui-kit/GameIcons";
import { moneyLabel } from "../format";

export default function CoinAmount({ value }: { value: number }) {
  return <span className="dala-coin-amount" aria-label={moneyLabel(value)}>
    <GameCoin size={17} /><span aria-hidden="true">{value.toLocaleString("kk-KZ")}</span>
  </span>;
}
