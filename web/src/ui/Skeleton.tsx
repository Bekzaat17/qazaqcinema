// Скелетон-заглушка (мерцание описано в index.css как .skeleton).

export default function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-xl ${className}`} />;
}
