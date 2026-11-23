const dateTime = new Intl.DateTimeFormat("pt-BR", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const dateOnly = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short" });
const time = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });

const toDate = (v: string | number | Date | null | undefined): Date | null => {
  if (v == null) return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
};

/** "12 nov, 14:32" */
export function formatDateTime(v: string | number | Date | null | undefined): string {
  const d = toDate(v);
  return d ? dateTime.format(d).replace(" de ", " ").replace(".", "") : "—";
}

/** "12 nov" */
export function formatDate(v: string | number | Date | null | undefined): string {
  const d = toDate(v);
  return d ? dateOnly.format(d).replace(" de ", " ").replace(".", "") : "—";
}

/** "14:32" */
export function formatTime(v: string | number | Date | null | undefined): string {
  const d = toDate(v);
  return d ? time.format(d) : "—";
}

/** Relativo curto para listas: "agora", "há 3 min", "há 2 h", "ontem", "12 nov". */
export function formatRelative(
  v: string | number | Date | null | undefined,
  now: Date = new Date()
): string {
  const d = toDate(v);
  if (!d) return "—";
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `há ${diffMin} min`;
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (d >= startOfToday) return `há ${Math.floor(diffMin / 60)} h`;
  const startOfYesterday = new Date(startOfToday.getTime() - 86400000);
  if (d >= startOfYesterday) return "ontem";
  return formatDate(d);
}
