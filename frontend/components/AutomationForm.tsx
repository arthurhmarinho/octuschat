"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Images, Image as ImageIcon, Sparkles, Plus, X } from "lucide-react";
import AppShell from "@/components/AppShell";
import DmPreview from "@/components/DmPreview";
import PostPicker from "@/components/PostPicker";
import { useAccount } from "@/lib/account";

type Trigger = "comment_any" | "comment_keyword" | "dm_keyword" | "dm_any";
type Scope = "all" | "specific" | "next";
type Button = { label: string; url: string };
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
  buttons: Button[];
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
  buttons: [],
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
  const [buttons, setButtons] = useState<Button[]>(start.buttons);
  const [save, setSave] = useState<SaveState>({ kind: "idle" });

  const addButton = () =>
    setButtons((b) => (b.length >= 3 ? b : [...b, { label: "", url: "" }]));
  const removeButton = (i: number) =>
    setButtons((b) => b.filter((_, idx) => idx !== i));
  const updateButton = (i: number, field: keyof Button, value: string) =>
    setButtons((b) => b.map((x, idx) => (idx === i ? { ...x, [field]: value } : x)));

  const isComment = trigger === "comment_any" || trigger === "comment_keyword";
  const isKeyword = trigger === "comment_keyword" || trigger === "dm_keyword";

  async function handleSave() {
    if (!isEdit && !accountId) {
      setSave({ kind: "error", msg: "Nenhuma conta do Instagram conectada." });
      return;
    }
    const cleanButtons = buttons
      .map((b) => ({ label: b.label.trim(), url: b.url.trim() }))
      .filter((b) => b.label && b.url);
    if (cleanButtons.some((b) => !/^https?:\/\//i.test(b.url))) {
      setSave({ kind: "error", msg: "A URL do botão precisa começar com http:// ou https://" });
      return;
    }
    setSave({ kind: "saving" });
    const payload: Record<string, unknown> = {
      name,
      trigger,
      keyword: isKeyword ? keyword : null,
      exclude_keywords: excludeKeywords || null,
      // Escopo de post e resposta pública só valem para gatilhos de comentário.
      post_id: isComment && scope === "specific" ? postId || null : null,
      bind_next: isComment && scope === "next",
      reply_message: replyMessage,
      public_reply: isComment ? publicReply || null : null,
      buttons: cleanButtons.length ? cleanButtons : null,
      link_url: null,
      link_label: null,
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
                <optgroup label="Comentário no post">
                  <option value="comment_keyword">Comentário com palavra-chave</option>
                  <option value="comment_any">Qualquer comentário</option>
                </optgroup>
                <optgroup label="Mensagem direta (DM)">
                  <option value="dm_keyword">Palavra-chave na DM</option>
                  <option value="dm_any">Qualquer DM (resposta padrão)</option>
                </optgroup>
              </select>
            </div>

            {isKeyword && (
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

            {isComment && (
            <div>
              <label className={labelCls}>Aplicar em</label>
              <div className="grid grid-cols-3 gap-3">
                {(
                  [
                    { v: "all", Icon: Images, t: "Todas", d: "Qualquer post ou Reel." },
                    { v: "specific", Icon: ImageIcon, t: "Específica", d: "Escolha um post." },
                    { v: "next", Icon: Sparkles, t: "Próxima", d: "O próximo que você postar." },
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

              {scope === "next" && (
                <p className="mt-2 rounded-lg border border-dashed border-[var(--border)] p-3 text-xs text-[var(--muted)]">
                  A automação vai se ativar no <strong>próximo post ou Reel</strong> que você
                  publicar — assim que ele receber o primeiro comentário. Ideal para criar a
                  regra antes de postar.
                </p>
              )}
            </div>
            )}

            {!isComment && (
              <p className="rounded-lg border border-dashed border-[var(--border)] p-3 text-xs text-[var(--muted)]">
                Gatilho de <strong>mensagem direta</strong>: responde quando alguém te
                envia uma DM {trigger === "dm_keyword" ? "com a palavra-chave" : "(qualquer mensagem)"}.
              </p>
            )}

            <div>
              <label className={labelCls}>Mensagem (texto) — vai na DM</label>
              <textarea
                className={`${inputCls} min-h-[110px] resize-y`}
                value={replyMessage}
                onChange={(e) => setReplyMessage(e.target.value)}
                placeholder="Oi! Obrigado pelo comentário 💜"
              />
            </div>

            {isComment && (
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
            )}

            <div>
              <label className={labelCls}>Botões de link (até 3)</label>
              <div className="space-y-2">
                {buttons.map((b, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      className={inputCls}
                      value={b.label}
                      onChange={(e) => updateButton(i, "label", e.target.value)}
                      placeholder="Rótulo (ex.: Acessar oferta)"
                    />
                    <input
                      className={inputCls}
                      value={b.url}
                      onChange={(e) => updateButton(i, "url", e.target.value)}
                      placeholder="https://..."
                    />
                    <button
                      type="button"
                      onClick={() => removeButton(i)}
                      title="Remover"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--muted)] hover:bg-red-500/10 hover:text-red-400"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
              {buttons.length < 3 && (
                <button
                  type="button"
                  onClick={addButton}
                  className="mt-2 inline-flex items-center gap-1.5 text-sm text-[var(--gold)] hover:underline"
                >
                  <Plus size={14} /> Adicionar botão
                </button>
              )}
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
              buttons={buttons}
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
