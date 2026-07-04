// Скелетон главного экрана на время загрузки каталога (мобильная сеть).

import Skeleton from "../ui/Skeleton";

function ShelfSkeleton() {
  return (
    <div className="mt-6">
      <Skeleton className="mx-4 mb-3 h-5 w-40" />
      <div className="no-scrollbar flex gap-3 overflow-hidden px-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3] w-[132px] shrink-0" />
        ))}
      </div>
    </div>
  );
}

export default function HomeSkeleton() {
  return (
    <div>
      <Skeleton className="aspect-[3/4] max-h-[560px] w-full rounded-none" />
      <ShelfSkeleton />
      <ShelfSkeleton />
    </div>
  );
}
