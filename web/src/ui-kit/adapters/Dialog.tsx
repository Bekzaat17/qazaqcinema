import { useEffect, useRef, type ReactNode } from "react";
import { X } from "./icons";
import { ButtonAdapter } from "./react";

export default function Dialog({ title, eyebrow, onClose, children, className = "", theme }:
  { title: string; eyebrow?: ReactNode; onClose: () => void; children: ReactNode;
    className?: string; theme?: "steppe" | "cinema" }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className={`ui-dialog ${className}`} data-ui-theme={theme}
    aria-label={title} onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <div className="ui-dialog-heading">
      <div>{eyebrow && <span className="ui-eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>
      <ButtonAdapter variant="ghost" size="sm" block={false} aria-label="Жабу" onClick={onClose}>
        <X size={21} />
      </ButtonAdapter>
    </div>
    {children}
  </dialog>;
}
