"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { ApiError, fetchBlob } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ScanThumb({
  id,
  token,
  hasImage,
  alt = "Label capture",
  className,
}: {
  id: string;
  token: string;
  hasImage: boolean;
  alt?: string;
  className?: string;
}): React.JSX.Element {
  const image = useQuery({
    queryKey: ["scan-image", id],
    queryFn: async () => {
      const blob = await fetchBlob(`/scans/${id}/image`, token);
      return URL.createObjectURL(blob);
    },
    // NOTE: intentionally NOT gated on hasImage. Older backends omit the flag
    // (zod defaults it to false) even when a blob exists, and old rows truly
    // have no blob (404 -> "No photo"). Always trying is correct for ≤10/page.
    enabled: !!token && !!id,
    staleTime: Infinity,
    retry: false,
  });

  React.useEffect(() => {
    const url = image.data;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [image.data]);

  if (image.isPending) {
    return (
      <span
        className={cn("block h-12 w-12 flex-none animate-pulse rounded-md bg-slate-200", className)}
        aria-label="Loading photo…"
      />
    );
  }
  if (image.isError || !image.data) {
    const missing =
      image.error instanceof ApiError ? image.error.status === 404 : !hasImage;
    return (
      <span
        className={cn(
          "grid h-12 w-12 flex-none place-items-center rounded-md border border-dashed border-slate-300 bg-slate-50 text-center text-[10px] font-bold leading-tight text-slate-400",
          className
        )}
      >
        {missing ? "No photo" : "Unavailable"}
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={image.data} alt={alt} className={cn("h-12 w-12 flex-none rounded-md border border-slate-200 object-cover", className)} loading="lazy" />;
}
