import type { ReactNode } from "react";
import { Brand, Dialog } from "../../ui-kit";

export default function QuestDialog({ title, onClose, children, className = "" }:
  { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  return <Dialog title={title} eyebrow={<Brand mark={false} compact />} theme="steppe"
    className={`quest-dialog ${className}`} onClose={onClose}>{children}</Dialog>;
}
