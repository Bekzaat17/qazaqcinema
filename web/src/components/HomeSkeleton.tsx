// Скелетон главного экрана на время загрузки каталога (мобильная сеть).

import Skeleton from "../ui/Skeleton";

function ShelfSkeleton() {
  return (
    <div className="mt-6">
      <Skeleton className="mx-4 mb-3 h-5 w-40" />
      <div className="no-scrollbar flex gap-3 overflow-hidden px-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3] w-[132px] shrink-0 sm:w-[150px]" />
        ))}
      </div>
    </div>
  );
}

export default function HomeSkeleton() {
  return (
    <div>
      {/* Высота — ровно как у `Hero`, и по той же причине задана явно: скелетон должен
          занимать место будущего блока, иначе экран прыгает на подстановке. */}
      <Skeleton className="h-[min(75vw,300px)] max-h-[60vh] w-full rounded-none sm:h-[340px] md:h-[380px]" />
      <ShelfSkeleton />
      <ShelfSkeleton />
    </div>
  );
}
