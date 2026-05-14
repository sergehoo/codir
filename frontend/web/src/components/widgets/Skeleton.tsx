import { cn } from '@/utils/cn'

type Props = { className?: string; width?: string; height?: string }

export function Skeleton({ className, width, height }: Props) {
  return (
    <div
      className={cn('animate-soft-pulse rounded-md bg-fg/[0.06]', className)}
      style={{ width, height }}
    />
  )
}

/** Skeleton ligne — typique pour une row dans une liste. */
export function SkeletonRow({ className }: { className?: string }) {
  return (
    <div className={cn('card p-5 flex items-center gap-4', className)}>
      <Skeleton className="w-8 h-8 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-2 w-1/3" />
      </div>
      <Skeleton className="h-6 w-16" />
    </div>
  )
}

/** Skeleton card grid — pour les listings. */
export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => <SkeletonRow key={i} />)}
    </div>
  )
}
