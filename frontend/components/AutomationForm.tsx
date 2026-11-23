"use client";

import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, Image as ImageIcon, Images, Plus, Trash2, X } from "lucide-react";
import AppShell from "@/components/AppShell";
import DmPreview from "@/components/DmPreview";
import FlowCanvas, { MAX_MESSAGES } from "@/components/FlowCanvas";
import PostPicker from "@/components/PostPicker";
import {
  Button,
  Card,
  Field,
  IconButton,
  Input,
  KeywordTokens,
  Note,
  Segmented,
  Select,
  Textarea,
} from "@/components/ui";
import { useAccount } from "@/lib/account";
import { TRIGGER_TEXT, type Trigger } from "@/lib/automation";
import {
  cleanMessages,
  editorToGraph,
  graphToEditor,
  isLinear,
  newNodeId,
  type EditorMessage,
  type FlowGraph,
  type GraphButton,
} from "@/lib/flowGraph";

type Scope = "all" | "specific" | "next";
type SaveState = { kind: "idle" | "saving" | "ok" | "error"; msg?: string };

const MAX_BUTTONS = 3;
const MAX_TEXT = 1000;

export type AutomationInitial = {
  name: string;
  trigger: Trigger;
  keyword: string;
  excludeKeywords: string;
  postId: string;
  scope: Scope;
  publicReply: string;
  /** Grafo salvo (null = automação nova). */
  graph: FlowGraph | null;
};

const EMPTY: AutomationInitial = {
  name: "",
  trigger: "comment_keyword",
  keyword: "",
  excludeKeywords: "",
  postId: "",
  scope: "all",
  publicReply: "",
  graph: null,
};

const urlInvalid = (b: GraphButton) => !!b.url.trim() && !/^https?:\/\//i.test(b.url.trim());

/** Texto humano para uma resposta de erro da API. */
async function describeError(res: Response): Promise<string> {
  if (res.status === 422) {
    try {
      const body = await res.json();
      const d = body?.detail;
      const msg = Array.isArray(d) ? d[0]?.msg : typeof d === "string" ? d : null;
      if (msg) return msg;
    } catch {
      /* cai no genérico */
    }
    return "Alguns campos estão inválidos. Revise e tente de novo";
  }
  if (res.status === 401 || res.status === 403) return "Sua sessão expirou. Entre de novo";
  return "Não foi possível salvar. Tente de novo em alguns segundos";
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="text-[15px] font-medium text-fg">{title}</h2>
      <p className="mb-3 mt-1 text-[13px] text-fg-2">{description}</p>
      {children}
    </section>
  );
}

export default function AutomationForm({
  automationId,
  initial,
}: {
  automationId?: number;
  initial?: AutomationInitial;
}) {
  const router = useRouter();
  const { account, accountId } = useAccount();
  const start = initial ?? EMPTY;
  const isEdit = automationId != null;

  const [name, setName] = useState(start.name);
  const [trigger, setTrigger] = useState<Trigger>(start.trigger);
  const [keyword, setKeyword] = useState(start.keyword);
  const [excludeKeywords, setExcludeKeywords] = useState(start.excludeKeywords);
  const [scope, setScope] = useState<Scope>(start.scope);
  const [postId, setPostId] = useState(start.postId);
  const [publicReply, setPublicReply] = useState(start.publicReply);
  const [messages, setMessages] = useState<EditorMessage[]>(() => graphToEditor(start.graph).messages);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [save, setSave] = useState<SaveState>({ kind: "idle" });

  // Grafo com condições: o editor não sabe editá-lo. Fica só leitura e o PATCH
  // não envia `graph`, então os ramos nunca são sobrescritos.
  const hasBranches = !isLinear(start.graph);

  const selected = messages.find((m) => m.id === selectedId) ?? messages[0];
  const selectedIndex = messages.findIndex((m) => m.id === selected.id);

  const updateMessage = (id: string, patch: Partial<EditorMessage>) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  const addMessage = () => {
    if (messages.length >= MAX_MESSAGES) return;
    const m: EditorMessage = { id: newNodeId(), text: "", buttons: [] };
    setMessages((ms) => [...ms, m]);
    setSelectedId(m.id);
  };
  const removeMessage = (id: string) => {
    if (messages.length <= 1) return;
    const idx = messages.findIndex((m) => m.id === id);
    const next = messages.filter((m) => m.id !== id);
    setMessages(next);
    if (selected.id === id) setSelectedId(next[Math.max(0, idx - 1)].id);
  };
  const reorder = (ids: string[]) => {
    const byId = new Map(messages.map((m) => [m.id, m]));
    setMessages(ids.map((id) => byId.get(id)).filter((m): m is EditorMessage => !!m));
  };

  const setButtons = (id: string, fn: (b: GraphButton[]) => GraphButton[]) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, buttons: fn(m.buttons) } : m)));

  const isComment = trigger === "comment_any" || trigger === "comment_keyword";
  const isKeyword = trigger === "comment_keyword" || trigger === "dm_keyword";
  const isStoryReply = trigger === "story_reply";
  // Story reply aceita palavra-chave OPCIONAL (vazia = qualquer resposta);
  // menção em story não tem texto, então não usa palavra-chave.
  const showKeyword = isKeyword || isStoryReply;
  const activeKeyword = showKeyword ? keyword : "";

  // Preview: botões ainda incompletos também aparecem.
  const previewGraph = hasBranches && start.graph ? start.graph : editorToGraph(messages, start.graph);

  const anyUrlInvalid = messages.some((m) => m.buttons.some(urlInvalid));

  async function handleSave() {
    if (!isEdit && !accountId) {
      setSave({ kind: "error", msg: "Conecte uma conta do Instagram antes de salvar" });
      return;
    }
    if (!hasBranches) {
      if (!messages[0]?.text.trim()) {
        setSelectedId(messages[0].id);
        setSave({ kind: "error", msg: "Escreva a mensagem 1" });
        return;
      }
      if (anyUrlInvalid) {
        setSave({ kind: "error", msg: "A URL do botão precisa começar com http:// ou https://" });
        return;
      }
    }
    setSave({ kind: "saving" });
    const payload: Record<string, unknown> = {
      name,
      trigger,
      keyword: showKeyword ? keyword || null : null,
      exclude_keywords: excludeKeywords || null,
      // Escopo de post e resposta pública só valem para gatilhos de comentário.
      post_id: isComment && scope === "specific" ? postId || null : null,
      bind_next: isComment && scope === "next",
      public_reply: isComment ? publicReply || null : null,
    };
    if (!hasBranches) payload.graph = editorToGraph(cleanMessages(messages), start.graph);
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
        setSave({ kind: "ok", msg: "Salvo" });
        router.push("/automations");
      } else {
        setSave({ kind: "error", msg: await describeError(res) });
      }
    } catch {
      setSave({ kind: "error", msg: "Não foi possível salvar. Verifique a conexão" });
    }
  }

  const saveButton = (
    <Button variant="primary" size="sm" onClick={handleSave} disabled={save.kind === "saving"}>
      {save.kind === "saving" ? "Salvando" : "Salvar"}
    </Button>
  );

  return (
    <AppShell
      title={isEdit ? name || "Editar automação" : "Nova automação"}
      back={{ href: "/automations", label: "Automações" }}
      action={saveButton}
    >
      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-8">
          {/* ── Gatilho ── */}
          <Section title="Gatilho" description="O que faz esta automação disparar">
            <Card className="space-y-5">
              <Field label="Nome" htmlFor="name">
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Promoção de lançamento"
                />
              </Field>

              <Field label="Gatilho" htmlFor="trigger">
                <Select
                  id="trigger"
                  value={trigger}
                  onChange={(e) => setTrigger(e.target.value as Trigger)}
                >
                  <optgroup label="Comentários">
                    <option value="comment_keyword">{TRIGGER_TEXT.comment_keyword}</option>
                    <option value="comment_any">{TRIGGER_TEXT.comment_any}</option>
                  </optgroup>
                  <optgroup label="Direct">
                    <option value="dm_keyword">{TRIGGER_TEXT.dm_keyword}</option>
                    <option value="dm_any">{TRIGGER_TEXT.dm_any}</option>
                  </optgroup>
                  <optgroup label="Stories">
                    <option value="story_reply">{TRIGGER_TEXT.story_reply}</option>
                    <option value="story_mention">{TRIGGER_TEXT.story_mention}</option>
                  </optgroup>
                </Select>
              </Field>

              {showKeyword && (
                <Field
                  label={isStoryReply ? "Palavra-chave (opcional)" : "Palavra-chave"}
                  htmlFor="keyword"
                  hint={
                    isStoryReply
                      ? "Deixe vazio para responder a qualquer resposta ao seu story"
                      : "Separe várias palavras com vírgula"
                  }
                >
                  <Input
                    id="keyword"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="preço, valor"
                  />
                  {keyword.trim() && (
                    <div className="mt-2">
                      <KeywordTokens value={keyword} />
                    </div>
                  )}
                </Field>
              )}

              <Field
                label="Palavras a excluir (opcional)"
                htmlFor="exclude"
                hint="Se a mensagem tiver uma destas palavras, a automação não dispara"
              >
                <Input
                  id="exclude"
                  value={excludeKeywords}
                  onChange={(e) => setExcludeKeywords(e.target.value)}
                  placeholder="spam, cancelar"
                />
              </Field>

              {isComment && (
                <div>
                  <p className="mb-2 text-[13px] font-medium text-fg-2">Aplicar em</p>
                  <Segmented<Scope>
                    aria-label="Aplicar em"
                    value={scope}
                    onChange={setScope}
                    options={[
                      { value: "all", label: "Todas", icon: Images },
                      { value: "specific", label: "Específica", icon: ImageIcon },
                      { value: "next", label: "Próxima", icon: CalendarClock },
                    ]}
                  />

                  {scope === "specific" && accountId && (
                    <div className="mt-3">
                      <PostPicker accountId={accountId} value={postId} onChange={setPostId} />
                    </div>
                  )}
                  {scope === "next" && (
                    <Note className="mt-3">
                      A automação passa a valer no próximo post ou Reel que você publicar, assim que
                      ele receber o primeiro comentário. Dá para criar a regra antes de postar
                    </Note>
                  )}
                </div>
              )}
            </Card>
          </Section>

          {/* ── Mensagens ── */}
          <Section
            title="Mensagens"
            description="A sequência enviada em direct quando o gatilho dispara"
          >
            <div className="space-y-3">
              <FlowCanvas
                messages={messages}
                selectedId={selected.id}
                triggerLabel={TRIGGER_TEXT[trigger]}
                triggerKeywords={activeKeyword}
                readOnly={hasBranches}
                onSelect={setSelectedId}
                onReorder={reorder}
                onAdd={addMessage}
              />

              {hasBranches ? (
                <Note variant="warning">
                  Este fluxo tem condições, que ainda não podem ser editadas aqui. Você pode mudar o
                  gatilho; as mensagens ficam como estão
                </Note>
              ) : (
                <>
                  <Card className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-fg">Mensagem {selectedIndex + 1}</h3>
                      {selectedIndex > 0 && (
                        <IconButton
                          icon={Trash2}
                          tone="danger"
                          aria-label={`Excluir mensagem ${selectedIndex + 1}`}
                          onClick={() => removeMessage(selected.id)}
                        />
                      )}
                    </div>

                    <Field label="Texto" htmlFor="msg-text">
                      <Textarea
                        id="msg-text"
                        rows={4}
                        maxLength={MAX_TEXT}
                        value={selected.text}
                        onChange={(e) => updateMessage(selected.id, { text: e.target.value })}
                        placeholder={selectedIndex === 0 ? "Oi! Obrigado pelo contato" : `Mensagem ${selectedIndex + 1}`}
                      />
                      <p className="mt-2 text-right font-mono text-xs tabular-nums text-fg-3">
                        {selected.text.length}/{MAX_TEXT}
                      </p>
                    </Field>

                    <div>
                      <p className="mb-2 text-[13px] font-medium text-fg-2">Botões de link</p>
                      <div className="space-y-2">
                        {selected.buttons.map((b, i) => (
                          <div key={i}>
                            <div className="flex items-center gap-2">
                              <Input
                                aria-label={`Rótulo do botão ${i + 1}`}
                                value={b.label}
                                onChange={(e) =>
                                  setButtons(selected.id, (bs) =>
                                    bs.map((x, j) => (j === i ? { ...x, label: e.target.value } : x))
                                  )
                                }
                                placeholder="Acessar oferta"
                              />
                              <Input
                                aria-label={`URL do botão ${i + 1}`}
                                aria-invalid={urlInvalid(b) || undefined}
                                value={b.url}
                                onChange={(e) =>
                                  setButtons(selected.id, (bs) =>
                                    bs.map((x, j) => (j === i ? { ...x, url: e.target.value } : x))
                                  )
                                }
                                placeholder="https://"
                              />
                              <IconButton
                                icon={X}
                                aria-label={`Remover botão ${i + 1}`}
                                onClick={() =>
                                  setButtons(selected.id, (bs) => bs.filter((_, j) => j !== i))
                                }
                              />
                            </div>
                            {urlInvalid(b) && (
                              <p className="mt-1.5 text-xs text-negative">
                                A URL precisa começar com http:// ou https://
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Plus}
                        className="mt-2 -ml-3"
                        disabled={selected.buttons.length >= MAX_BUTTONS}
                        onClick={() =>
                          setButtons(selected.id, (bs) => [...bs, { label: "", url: "" }])
                        }
                      >
                        Adicionar botão
                      </Button>
                    </div>
                  </Card>

                  {isComment && messages.length >= 2 && (
                    <Note variant="warning">
                      A mensagem 1 sai como resposta privada ao comentário. As seguintes só são
                      enviadas se a pessoa tiver mandado uma DM para você nas últimas 24 horas
                    </Note>
                  )}
                </>
              )}
            </div>
          </Section>

          {/* ── Resposta pública ── */}
          {isComment && (
            <Section
              title="Resposta pública"
              description="Opcional. Um comentário seu abaixo do comentário original"
            >
              <Card>
                <Field
                  label="Texto"
                  htmlFor="public-reply"
                  hint="Publicada como resposta ao comentário, depois da DM"
                >
                  <Textarea
                    id="public-reply"
                    rows={2}
                    value={publicReply}
                    onChange={(e) => setPublicReply(e.target.value)}
                    placeholder="Te mandei no direct"
                  />
                </Field>
              </Card>
            </Section>
          )}

          <p
            role="status"
            className={save.kind === "error" ? "text-[13px] text-negative" : "text-[13px] text-fg-2"}
          >
            {save.msg}
          </p>
        </div>

        {/* ── Prévia ── */}
        <div className="lg:sticky lg:top-[72px] lg:self-start">
          <p className="mb-3 text-[13px] text-fg-2">Prévia</p>
          <DmPreview
            username={account?.username ?? ""}
            graph={previewGraph}
            isComment={isComment}
            selectedId={hasBranches ? null : selected.id}
          />
        </div>
      </div>
    </AppShell>
  );
}
