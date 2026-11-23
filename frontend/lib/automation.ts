export type Trigger =
  | "comment_any"
  | "comment_keyword"
  | "dm_keyword"
  | "dm_any"
  | "story_reply"
  | "story_mention";

/** Gatilho em texto corrido (listas e cards). */
export const TRIGGER_TEXT: Record<Trigger, string> = {
  comment_keyword: "Comentário com palavra-chave",
  comment_any: "Qualquer comentário",
  dm_keyword: "DM com palavra-chave",
  dm_any: "Qualquer DM",
  story_reply: "Resposta ao story",
  story_mention: "Menção em story",
};

/** Origem de uma mensagem (campo `source` da API) em texto curto. */
export function sourceLabel(source: string): string {
  if (source.startsWith("comment")) return "comentário";
  if (source.startsWith("story")) return "story";
  return "DM";
}
