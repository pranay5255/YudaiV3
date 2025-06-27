import "./globals.css";
import { GeistSans } from "geist/font/sans";
import { Toaster } from "sonner";
import { cn } from "@/lib/utils";


export const metadata = {
  title: "YudaiV3",
  description:
    "Your Product Assistant for your Github Repositories",
  openGraph: {
    images: [
      {
        url: "/og?title=YudaiV3",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: [
      {
        url: "/og?title=AI SDK Python Streaming Preview",
      },
    ],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head></head>
      <body className={cn(GeistSans.className, "antialiased dark")}>
        <Toaster position="top-center" richColors />
        {children}
      </body>
    </html>
  );
}
