"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ToasterProvider, useToast } from "@/components/ui/toaster";
import { ApiError } from "@/lib/api";

function QueryBridge({ children }: { children: React.ReactNode }): React.JSX.Element {
  const { notifyError } = useToast();
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false },
          mutations: {
            onError: (e: unknown) =>
              notifyError(e, e instanceof ApiError ? e.message : "Something went wrong."),
          },
        },
      })
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

export function Providers({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <ToasterProvider>
      <QueryBridge>{children}</QueryBridge>
    </ToasterProvider>
  );
}
