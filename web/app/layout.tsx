import type { Metadata } from "next";

import { AuthProvider } from "@/components/auth-context";
import { Chrome } from "@/components/chrome";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "LMPC Compliance Scanner",
  description: "Legal Metrology (Packaged Commodities) Rules, 2011 — label compliance dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <html lang="en">
      <body className="bg-slate-100 text-slate-900 antialiased">
        <Providers>
          <AuthProvider>
            <Chrome>{children}</Chrome>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
