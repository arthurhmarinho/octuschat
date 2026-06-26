/**
 * Monta o corpo da DM a partir de texto + link opcional.
 * Espelha `compose_message` do backend (automation_engine.py) para que o
 * preview ao vivo seja fiel ao que será realmente enviado.
 */
export function composeMessage(
  text: string,
  linkUrl?: string,
  linkLabel?: string
): string {
  if (!linkUrl) return text;
  if (linkLabel) return `${text}\n\n👉 ${linkLabel}: ${linkUrl}`;
  return `${text}\n\n${linkUrl}`;
}
