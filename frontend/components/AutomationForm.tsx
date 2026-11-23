"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, ChevronDown, Image as ImageIcon, Images } from "lucide-react";
import AppShell from "@/components/AppShell";
import FlowEditor from "@/components/flow/FlowEditor";
import { useFlowHistory } from "@/components/flow/useFlowHistory";
import { validateGraph } from "@/components/flow/validateGraph";
import PostPicker from "@/components/PostPicker";
import {
  Button,
  Card,
  Field,
  Input,
  KeywordTokens,
  Note,
  Segmented,
  Select,
  Textarea,
  useFeedback,
} from "@/components/ui";
import { useAccount } from "@/lib/account";
import { TRIGGER_TEXT, type Trigger } from "@/lib/automation";
import { normalizeGraph, toApiGraph, type FlowGraph } from "@/lib/flowGraph";

type Scope = "all" | "specific" | "next";
type SaveState = { kind: "idle" | "saving" | "ok" | "error"; msg?: string };

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
  const { toast, confirm } = useFeedback();
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
  const flow = useFlowHistory(normalizeGraph(start.graph));
  const [save, setSave] = useState<SaveState>({ kind: "idle" });
  const [triggerOpen, setTriggerOpen] = useState(!isEdit);

  // ── Alterações não salvas ──
  // A "foto" inicial é tirada no primeiro render; qualquer diferença depois dela é edição.
  const snapshot = JSON.stringify({
    name,
    trigger,
    keyword,
    excludeKeywords,
    scope,
    postId,
    publicReply,
    graph: flow.graph,
  });
  const baseline = useRef<string | null>(null);
  if (baseline.current === null) baseline.current = snapshot;
  const dirty = snapshot !== baseline.current;
  // Depois de salvar, a navegação para a lista não deve pedir confirmação.
  const leaving = useRef(false);
  const saveRef = useRef<() => void>(() => {});

  useEffect(() => {
    if (!dirty) return;

    // Fechar/recarregar a aba.
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!leaving.current) e.preventDefault();
    };
    // Clique em qualquer link interno (sidebar, "Automações").
    const onClick = async (e: MouseEvent) => {
      if (leaving.current || e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a || a.target === "_blank" || a.origin !== window.location.origin) return;
      if (a.pathname === window.location.pathname) return;
      e.preventDefault();
      e.stopPropagation();
      const ok = await confirm({
        title: "Sair sem salvar?",
        description: "As alterações desta automação serão perdidas",
        confirmLabel: "Sair sem salvar",
        cancelLabel: "Continuar editando",
        tone: "danger",
      });
      if (ok) {
        leaving.current = true;
        router.push(a.pathname + a.search);
      }
    };
    // Ctrl/Cmd+S salva.
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        saveRef.current();
      }
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onClick, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [dirty, confirm, router]);

  const isComment = trigger === "comment_any" || trigger === "comment_keyword";
  const isKeyword = trigger === "comment_keyword" || trigger === "dm_keyword";
  const isStoryReply = trigger === "story_reply";
  // Story reply aceita palavra-chave OPCIONAL (vazia = qualquer resposta);
  // menção em story não tem texto, então não usa palavra-chave.
  const showKeyword = isKeyword || isStoryReply;
  const activeKeyword = showKeyword ? keyword : "";

  // Erros bloqueiam o salvar; avisos não. O backend valida de novo (o front pode ser contornado).
  const validation = validateGraph(flow.graph, trigger);

  async function handleSave() {
    if (!isEdit && !accountId) {
      fail("Conecte uma conta do Instagram antes de salvar");
      return;
    }
    if (validation.errors.length) {
      fail(validation.errors[0].message);
      return;
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
    payload.graph = toApiGraph(flow.graph);
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
        leaving.current = true;
        toast(isEdit ? "Automação salva" : "Automação criada");
        router.push("/automations");
      } else {
        fail(await describeError(res));
      }
    } catch {
      fail("Não foi possível salvar. Verifique a conexão");
    }
  }
  saveRef.current = () => {
    if (save.kind !== "saving") void handleSave();
  };

  /** Erro no estado do formulário e num aviso, já que o texto fixo fica no fim da página. */
  function fail(msg: string) {
    setSave({ kind: "error", msg });
    toast(msg, "error");
  }

  const saveButton = (
    <div className="flex items-center gap-3">
      {dirty && save.kind !== "saving" && (
        <span className="hidden items-center gap-2 text-[13px] text-fg-3 sm:flex">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-warning" />
          Alterações não salvas
        </span>
      )}
      <Button
        variant="primary"
        size="sm"
        onClick={handleSave}
        disabled={save.kind === "saving" || validation.errors.length > 0}
        title={validation.errors.length ? "Resolva os problemas do fluxo para salvar" : undefined}
      >
        {save.kind === "saving" ? "Salvando" : "Salvar"}
      </Button>
    </div>
  );

  return (
    <AppShell
      wide
      title={isEdit ? name || "Editar automação" : "Nova automação"}
      back={{ href: "/automations", label: "Automações" }}
      action={saveButton}
    >
      <div className="space-y-8">
        {/* ── Gatilho (recolhível) ── */}
        <section>
          <button
            type="button"
            aria-expanded={triggerOpen}
            onClick={() => setTriggerOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-3 text-left"
          >
            <span>
              <span className="block text-[15px] font-medium text-fg">Gatilho</span>
              <span className="mt-1 block text-[13px] text-fg-2">
                {triggerOpen ? "O que faz esta automação disparar" : `${name || "Sem nome"} · ${TRIGGER_TEXT[trigger]}`}
              </span>
            </span>
            <ChevronDown
              size={16}
              strokeWidth={1.5}
              className={`shrink-0 text-fg-3 transition-transform duration-150 ease-out ${triggerOpen ? "rotate-180" : ""}`}
            />
          </button>

          {triggerOpen && (
            <Card className="mt-3 grid items-start gap-x-5 gap-y-4 md:grid-cols-2 xl:grid-cols-3">
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
                <div className="md:col-span-2 xl:col-span-3">
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
          )}
        </section>

        {/* ── Fluxo ── */}
        <section>
          <h2 className="text-[15px] font-medium text-fg">Fluxo</h2>
          <p className="mb-3 mt-1 text-[13px] text-fg-2">
            O que é enviado quando o gatilho dispara. Arraste os nós, ligue as saídas e use o + para
            continuar o caminho
          </p>
          <FlowEditor
            flow={flow}
            validation={validation}
            triggerLabel={TRIGGER_TEXT[trigger]}
            triggerKeywords={activeKeyword}
            username={account?.username ?? ""}
            isComment={isComment}
          />
        </section>

        {/* ── Resposta pública ── */}
        {isComment && (
          <Section
            title="Resposta pública"
            description="Opcional. Um comentário seu abaixo do comentário original"
          >
            <Card className="max-w-3xl">
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
          className={save.kind === "error" ? "text-[13px] text-negative" : "text-[13px] text-fg-2"}
        >
          {save.msg}
        </p>
      </div>
    </AppShell>
  );
}
