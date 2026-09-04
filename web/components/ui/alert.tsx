import * as React from "react";

import { cn } from "@/lib/utils";

const Alert = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn(
        "relative w-full rounded-md border px-4 py-3 text-sm [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4",
        className
      )}
      {...props}
    />
  )
);
Alert.displayName = "Alert";

const AlertDestructive = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <Alert ref={ref} className={cn("border-red-300 bg-red-50 text-red-900", className)} {...props} />
  )
);
AlertDestructive.displayName = "AlertDestructive";

const AlertInfo = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <Alert
      ref={ref}
      className={cn("border-sky-300 bg-sky-50 text-sky-900", className)}
      {...props}
    />
  )
);
AlertInfo.displayName = "AlertInfo";

export { Alert, AlertDestructive, AlertInfo };
