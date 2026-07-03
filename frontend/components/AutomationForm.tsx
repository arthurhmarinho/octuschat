"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Images, Image as ImageIcon } from "lucide-react";
import AppShell from "@/components/AppShell";
import DmPreview from "@/components/DmPreview";
import PostPicker from "@/components/PostPicker";
import { useAccount } from "@/lib/account";

type Trigger = "comment_any" | "comment_keyword";
type Scope = "all" | "specific";
type SaveState = { kind: "idle" | "saving" | "ok" | "error"; msg?: string };

export type AutomationInitial = {
  name: string;
  trigger: Trigger;
  keyword: string;
  excludeKeywords: string;
  postId: string;
  scope: Scope;
  replyMessage: string;
  publicReply: string;
  linkUrl: string;
  linkLabel: string;
};

const EMPTY: AutomationInitial = {
  name: "",
  trigger: "comment_keyword",
  keyword: "",
  excludeKeywords: "",
  postId: "",
  scope: "all",
  replyMessage: "",
  publicReply: "",
  linkUrl: "",
  linkLabel: "",
};

export default function AutomationForm({
  automationId,
  initial,
}: {
  automationId?: number;
  initial?: AutomationInitial;
}) {
  const router = useRouter();
  const { accountId } = useAccount();
  const start = initial ?? EMPTY;
  const isEdit = automationId != null;

  const [name, setName] = useState(start.name);
  const [trigger, setTrigger] = useState<Trigger>(start.trigger);
  const [keyword, setKeyword] = useState(start.keyword);
  const [excludeKeywords, setExcludeKeywords] = useState(start.excludeKeywords);
  const [scope, setScope] = useState<Scope>(start.scope);
  const [postId, setPostId] = useState(start.postId);
  const [replyMessage, setReplyMessage] = useState(start.replyMessage);
  const [publicReply, setPublicReply] = useState(start.publicReply);
  const [linkUrl, setLinkUrl] = useState(start.linkUrl);
  const [linkLabel, setLinkLabel] = useState(start.linkLabel);
  const [save, setSave] = useState<SaveState>({ kind: "idle" });

  async function handleSave() {
    if (!isEdit && !accountId) {
      setSave({ kind: "error", msg: "Nenhuma conta do Instagram conectada." });
      return;
    }
    setSave({ kind: "saving" });
    const payload: Record<string, unknown> = {
      name,
      trigger,
      keyword: trigger === "comment_keyword" ? keyword : null,
      exclude_keywords: excludeKeywords || null,
      post_id: scope === "specific" ? postId || null : null,
      reply_message: replyMessage,
      public_reply: publicReply || null,
      link_url: linkUrl || null,
      link_label: linkLabel || null,
    };
    if (!isEdit) payload.account_id = accountId;

    try {
      const res = await fetch(
        isEdit ? `/api/backend/automations/${automationId}` : "/api/backend/automations",
        {
          method: isEdit ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (res.ok) {
        setSave({ kind: "ok", msg: "Salvo!" });
        router.push("/automations");
      } else {
        const body = await res.text();
        setSave({ kind: "error", msg: `Erro ${res.status}: ${body.slice(0, 120)}` });
      }
    } catch {
      setSave({ kind: "error", msg: "Backend offline — o preview funciona normalmente." });
    }
  }

  const labelCls = "mono mb-1.5 block text-xs uppercase tracking-wide text-[var(--muted)]";
  const inputCls =
    "w-full rounded-lg border border-[var(--border)] bg-black/30 px-3.5 py-2.5 text-sm outline-none transition-colors focus:border-[var(--gold)]";

  return (
    <AppShell title={isEdit ? "Editar automação" : "Nova automação"}>
      <div className="mx-auto max-w-5xl">
        <Link
          href="/automations"
          className="mb-6 inline-flex items-center gap-2 text-sm text-[var(--muted)] hover:text-white"
        >
          <ArrowLeft size={16} /> Voltar para automações
        </Link>

        <p className="mb-8 text-sm text-[var(--muted)]">
          Quando alguém comentar, sua conta envia uma DM automática. O preview à
          direita atualiza enquanto você edita.
        </p>

        <div className="grid gap-10 md:grid-cols-2">
          {/* ── Formulário ── */}
          <div className="glass space-y-5 p-6">
            <div>
              <label className={labelCls}>Nome da automação</label>
              <input
                className={inputCls}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex.: Promoção de lançamento"
              />
            </div>

            <div>
              <label className={labelCls}>Gatilho</label>
              <select
                className={inputCls}
                value={trigger}
                onChange={(e) => setTrigger(e.target.value as Trigger)}
              >
                <option value="comment_keyword">Comentário com palavra-chave</option>
                <option value="comment_any">Qualquer comentário</option>
              </select>
            </div>

            {trigger === "comment_keyword" && (
              <div>
                <label className={labelCls}>Palavra-chave</label>
                <input
                  className={inputCls}
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="Ex.: quero"
                />
              </div>
            )}

            <div>
              <label className={labelCls}>Palavras a excluir (opcional)</label>
              <input
                className={inputCls}
                value={excludeKeywords}
                onChange={(e) => setExcludeKeywords(e.target.value)}
                placeholder="Ex.: não, spam, ódio (separadas por vírgula)"
              />
              <p className="mt-1 text-xs text-[var(--muted)]">
                Se o comentário contiver alguma dessas palavras, a automação não dispara.
              </p>
            </div>

            <div>
              <label className={labelCls}>Aplicar em</label>
              <div className="grid grid-cols-2 gap-3">
                {(
                  [
                    { v: "all", Icon: Images, t: "Todas as publicações", d: "Vale para qualquer post ou Reel." },
                    { v: "specific", Icon: ImageIcon, t: "Publicação específica", d: "Escolha um post ou Reel." },
                  ] as const
                ).map(({ v, Icon, t, d }) => {
                  const active = scope === v;
                  return (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setScope(v)}
                      className={`rounded-lg border p-3 text-left transition-colors ${
                        active
                          ? "border-[var(--gold)] bg-[var(--gold)]/10"
                          : "border-[var(--border)] hover:border-white/20"
                      }`}
                    >
                      <Icon size={18} className={active ? "text-[var(--gold)]" : "text-[var(--muted)]"} />
                      <p className="mt-2 text-sm font-medium">{t}</p>
                      <p className="text-xs text-[var(--muted)]">{d}</p>
                    </button>
                  );
                })}
              </div>

              {scope === "specific" && accountId && (
                <div className="mt-3">
                  <PostPicker accountId={accountId} value={postId} onChange={setPostId} />
                </div>
              )}
            </div>

            <div>
              <label className={labelCls}>Mensagem (texto) — vai na DM</label>
              <textarea
                className={`${inputCls} min-h-[110px] resize-y`}
                value={replyMessage}
                onChange={(e) => setReplyMessage(e.target.value)}
                placeholder="Oi! Obrigado pelo comentário 💜"
              />
            </div>

            <div>
              <label className={labelCls}>Resposta pública no comentário (opcional)</label>
              <input
                className={inputCls}
                value={publicReply}
                onChange={(e) => setPublicReply(e.target.value)}
                placeholder="Ex.: Enviei no seu direct 🚀"
              />
              <p className="mt-1 text-xs text-[var(--muted)]">
                Aparece como resposta pública no post — dá prova social e incentiva mais comentários.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Link (URL)</label>
                <input
                  className={inputCls}
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div>
                <label className={labelCls}>Rótulo do link</label>
                <input
                  className={inputCls}
                  value={linkLabel}
                  onChange={(e) => setLinkLabel(e.target.value)}
                  placeholder="Ex.: Acessar oferta"
                />
              </div>
            </div>

            <button
              onClick={handleSave}
              disabled={save.kind === "saving"}
              className="btn-gold inline-flex items-center gap-2 rounded-xl px-6 py-3 disabled:opacity-60"
            >
              {save.kind === "saving" && <Loader2 size={16} className="animate-spin" />}
              {isEdit ? "Salvar alterações" : "Salvar automação"}
            </button>

            {save.msg && (
              <p
                className={
                  save.kind === "ok"
                    ? "text-sm text-[var(--green)]"
                    : "text-sm text-amber-400"
                }
              >
                {save.msg}
              </p>
            )}
          </div>

          {/* ── Preview ao vivo ── */}
          <div className="md:sticky md:top-24 md:self-start">
            <p className="mono mb-3 text-center text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
              Preview da DM
            </p>
            <DmPreview
              username="sua_conta"
              text={replyMessage}
              linkUrl={linkUrl || undefined}
              linkLabel={linkLabel || undefined}
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
