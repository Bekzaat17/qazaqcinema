import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

export default function QuestDialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="quest-dialog"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="quest-dialog-heading">
        <div>
          <span className="quest-eyebrow">QAZAQQUEST</span>
          <h2>{title}</h2>
        </div>
        <button className="quest-icon" aria-label="Жабу" onClick={onClose}>
          <X size={21} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
