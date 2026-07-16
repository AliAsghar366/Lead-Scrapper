import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function safeUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  if (!url.startsWith("http")) return `https://${url}`;
  return url;
}
