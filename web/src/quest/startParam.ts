export function isQuestStartParam(value: string | null | undefined): boolean {
  return !!value && (["quest", "quest_rooms", "quest_create", "quest_create_public"].includes(value)
    || /^quest_room_[a-f0-9]{10}$/i.test(value));
}
