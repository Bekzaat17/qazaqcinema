import BuildingMiniature from "./illustration/BuildingMiniature";
import { useState, type CSSProperties } from "react";
import { Landmark, ShoppingBag, Plus, HandCoins } from "lucide-react";
import { groupIndices, rentFor } from "../rules";
import { money } from "../format";
import type { Action, Board, Match, Scenario } from "../types";

export default function PropertyPanel({
  board,
  match,
  me,
  selected,
  scenario,
  disabled,
  onCommand,
}: {
  board: Board;
  match: Match;
  me: number;
  selected: number;
  scenario: Scenario | undefined;
  disabled: boolean;
  onCommand: (
    kind: Action,
    target?: string,
    tile?: number,
    amount?: number,
  ) => void;
}) {
  const selectedTile = board.tiles[selected],
    selectedLot = match.lots[selected],
    owner = selectedLot ? match.players[selectedLot.owner] : null;
  const [offerAmount, setOfferAmount] = useState(
    String(Math.floor((selectedTile?.price ?? 100) * 1.5)),
  );
  const ownedSet =
    selected >= 0 &&
    groupIndices(board, selected).every(
      (i) => match.lots[i]?.owner === me && !match.lots[i].mortgaged,
    );
  const myTurn = me === match.turn && !match.players[me]?.bankrupt;
  const player = match.players[me];
  const send = onCommand;
  return selectedTile && board && match ? (
    <div className="dala-property-detail">
      <div
        className="dala-deed"
        style={{ "--deed-color": selectedTile.color } as CSSProperties}
      >
        <div>
          <span>МҮЛІК КАРТОЧКАСЫ</span>
          <h3>{selectedTile.name}</h3>
        </div>
        <div
          className={`dala-deed-scene ${board.illustration ? "dala-deed-rich-art" : ""}`}
        >
          {board.miniature_atlas ? (
            <svg
              viewBox="-75 -80 150 140"
              width="100%"
              height="100%"
              role="img"
              aria-label={
                selectedTile.landmark ||
                selectedTile.street ||
                selectedTile.name
              }
            >
              <BuildingMiniature
                board={board}
                tile={selectedTile}
                level={selectedLot?.level ?? 0}
              />
            </svg>
          ) : board.illustration ? (
            <img src={board.illustration} alt="" width="1536" height="1024" />
          ) : (
            <Landmark size={54} strokeWidth={1} />
          )}
          <span>
            {selectedLot?.level === 4
              ? "Қонақүй"
              : selectedLot?.level
                ? `${selectedLot.level} ғимарат`
                : "Дамытуға дайын"}
          </span>
        </div>
        <div className="dala-deed-owner">
          <i style={{ background: owner?.color ?? "#b9b7a3" }} />
          {owner ? owner.name : "Банк"}
          {selectedLot?.mortgaged && <span>Кепілде</span>}
        </div>
      </div>
      {["property", "station"].includes(selectedTile.kind) ? (
        <>
          <div className="dala-price-row">
            <span>Сатып алу</span>
            <b>{money(selectedTile.price)}</b>
          </div>
          <div className="dala-price-row">
            <span>Қазіргі жалдау ақысы</span>
            <b>
              {money(
                selectedLot
                  ? rentFor(board, match, selected)
                  : selectedTile.rents[0],
              )}
            </b>
          </div>
          {selectedTile.kind === "property" && (
            <div className="dala-rent-table">
              {selectedTile.rents.map((rent, i) => (
                <div
                  key={i}
                  className={selectedLot?.level === i ? "current" : ""}
                >
                  <span>
                    {i === 0
                      ? "Бастапқы"
                      : i === 4
                        ? "Қонақүй"
                        : `${i} ғимарат`}
                  </span>
                  <b>{money(rent)}</b>
                </div>
              ))}
              <small>
                Түсті топ толық жиналса, ғимаратсыз жалдау ақысы екі еселенеді.
              </small>
            </div>
          )}
          {!selectedLot &&
            myTurn &&
            match.phase === "buy" &&
            match.pending === selected && (
              <button
                className="dala-primary dala-full"
                disabled={disabled || player!.cash < selectedTile.price}
                onClick={() => send("buy")}
              >
                <ShoppingBag size={17} /> Сатып алу ·{" "}
                {money(selectedTile.price)}
              </button>
            )}
          {selectedLot?.owner === me && (
            <>
              <div className="dala-property-actions">
                {selectedTile.kind === "property" && (
                  <button
                    className="dala-primary"
                    disabled={
                      disabled ||
                      !myTurn ||
                      match.phase === "debt" ||
                      !ownedSet ||
                      selectedLot.mortgaged ||
                      selectedLot.level >= 4 ||
                      player!.cash < selectedTile.build_cost
                    }
                    onClick={() => send("build", "", selected)}
                  >
                    <Plus size={16} />
                    {selectedLot.level === 3
                      ? "Қонақүй салу"
                      : "Ғимарат салу"}{" "}
                    · {money(selectedTile.build_cost)}
                  </button>
                )}
                {selectedLot.level > 0 && (
                  <button
                    className="dala-secondary"
                    disabled={disabled || !myTurn}
                    onClick={() => send("sell", "", selected)}
                  >
                    Ғимаратты сату · +
                    {money(Math.floor(selectedTile.build_cost / 2))}
                  </button>
                )}
                <button
                  className="dala-secondary"
                  disabled={
                    disabled ||
                    !myTurn ||
                    match.phase === "finished" ||
                    (selectedLot.mortgaged &&
                      (match.phase === "debt" ||
                        player!.cash <
                          Math.ceil(Math.floor(selectedTile.price / 2) * 1.1)))
                  }
                  onClick={() =>
                    send(
                      selectedLot.mortgaged ? "redeem" : "mortgage",
                      "",
                      selected,
                    )
                  }
                >
                  {selectedLot.mortgaged
                    ? `Кепілден қайтару · ${money(Math.ceil(Math.floor(selectedTile.price / 2) * 1.1))}`
                    : `Кепілге қою · +${money(Math.floor(selectedTile.price / 2))}`}
                </button>
              </div>
              {!ownedSet && selectedTile.kind === "property" && (
                <p className="dala-muted">
                  Құрылыс үшін осы түстегі барлық кәсіп өзіңде және кепілден бос
                  болуы керек.
                </p>
              )}
            </>
          )}
          {selectedLot &&
            selectedLot.owner !== me &&
            player &&
            !player.bankrupt &&
            match.phase !== "finished" && (
              <div className="dala-offer-form">
                <label htmlFor="dala-offer">Сатып алуға ұсыныс, ₸</label>
                <div>
                  <input
                    id="dala-offer"
                    type="number"
                    min="1"
                    max="1000000"
                    value={offerAmount}
                    onChange={(e) => setOfferAmount(e.target.value)}
                  />
                  <button
                    className="dala-secondary"
                    disabled={
                      disabled ||
                      selectedLot.level > 0 ||
                      selectedLot.mortgaged ||
                      match.phase === "debt" ||
                      !Number.isInteger(Number(offerAmount)) ||
                      Number(offerAmount) < 1 ||
                      Number(offerAmount) > player.cash
                    }
                    onClick={() =>
                      send("offer", "", selected, Number(offerAmount))
                    }
                  >
                    <HandCoins size={17} /> Ұсыну
                  </button>
                </div>
                <small>
                  {owner?.bot
                    ? "Бот бастапқы бағаның кемінде 150%-ын қабылдайды."
                    : "Ұсынысты кәсіп иесі өз терезесінде қабылдайды немесе бас тартады."}
                </small>
              </div>
            )}
        </>
      ) : (
        <p className="dala-muted">
          {selectedTile.kind === "start"
            ? `Осы алаңнан өткенде ${money(scenario?.salary ?? 0)} айналым табысын аласың.`
            : selectedTile.kind === "chance"
              ? "Картаны ашып, кездейсоқ мүмкіндік немесе шығын аласың."
              : selectedTile.kind === "rest"
                ? `Наурыз сыйлығы: ${money(selectedTile.amount)}.`
                : `Төлем: ${money(selectedTile.amount * (scenario?.tax_multiplier ?? 1))}.`}
        </p>
      )}
    </div>
  ) : null;
}
