export const COIN_NAME = "Dala";
export const COIN_SYMBOL = "◈";
export const money = (value: number) => `${value.toLocaleString("kk-KZ")} ${COIN_SYMBOL}`;
export const moneyLabel = (value: number) => `${value.toLocaleString("kk-KZ")} Dala ойын монетасы`;
export const roundLimitLabel = (limit: number) => limit === 0 ? "Шектеусіз" : `${limit} айналым`;

// Сохранённые партии и серверный журнал могут содержать прежнее обозначение.
// Преобразование — только отображение; суммы и сохранённое состояние не меняются.
export const gameText = (value: string) => value
  .replace(/₸/g, COIN_SYMBOL)
  .replace(/теңгесі/gi, "монетасы")
  .replace(/теңге/gi, "ойын монетасы");
