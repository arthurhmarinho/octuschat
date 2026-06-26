"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import AppShell from "@/components/AppShell";
import DmPreview from "@/components/DmPreview";

type Trigger = "comment_any" | "comment_keyword";
type SaveState = { kind: "idle" | "saving" | "ok" | "error"; msg?: string };

export default function NewAutomationPage() {
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<Trigger>("comment_keyword");
  const [keyword, setKeyword] = useState("");
  const [replyMessage, setReplyMessage] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [save, setSave] = useState<SaveState>({ kind: "idle" });

  async function handleSave() {
    setSave({ kind: "saving" });
    try {
      const res = await fetch("/api/backend/automations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: "demo", // TODO: usar a conta conectada real
          name,
          trigger,
          keyword: trigger === "comment_keyword" ? keyword : null,
          reply_message: replyMessage,
          link_url: linkUrl || null,
          link_label: linkLabel || null,
        }),
      });
      if (res.ok) {
        setSave({ kind: "ok", msg: "Automação salva!" });
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
    <AppShell title="Nova automação">
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
              <label className={labelCls}>Mensagem (texto)</label>
              <textarea
                className={`${inputCls} min-h-[110px] resize-y`}
                value={replyMessage}
                onChange={(e) => setReplyMessage(e.target.value)}
                placeholder="Oi! Obrigado pelo comentário 💜"
              />
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
              Salvar automação
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
