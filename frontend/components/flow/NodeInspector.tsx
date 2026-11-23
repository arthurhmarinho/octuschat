"use client";

import { ArrowDown, ArrowUp, Plus, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import {
  Button,
  Field,
  IconButton,
  Input,
  Note,
  Segmented,
  Select,
  Textarea,
  cx,
} from "@/components/ui";
import {
  CONDITION_LABEL,
  MAX_BUTTONS,
  MAX_HOURS,
  MAX_QUICK_REPLIES,
  MIN_HOURS,
  NODE_LABEL,
  QUICK_REPLY_TITLE_MAX,
  VAR_RE,
  byteLength,
  newItemId,
  textLimit,
  variablesOf,
  type ConditionMode,
  type FlowGraph,
  type GraphNode,
  type MessageNode,
} from "@/lib/flowGraph";
import { formatHours } from "./nodes/nodeTypes";

type Patch = (patch: Partial<GraphNode>, key?: string) => void;

const isUrl = (s: string) => /^https?:\/\//i.test(s.trim());

/** Contador de bytes (n/limite), em mono, vermelho ao passar. */
function ByteCounter({ text, limit }: { text: string; limit: number }) {
  const n = byteLength(text);
  return (
    <p className={cx("mt-2 text-right font-mono text-xs tabular-nums", n > limit ? "text-negative" : "text-fg-3")}>
      {n}/{limit}
    </p>
  );
}

/** Campo de horas (0,1 a 23). Guarda o texto digitado e só envia números válidos. */
function HoursField({
  id,
  label,
  value,
  fallback,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: number | undefined;
  /** Valor mostrado quando o nó não define (ex.: 23 h de espera padrão). */
  fallback?: number;
  onChange: (n: number | undefined) => void;
  hint?: string;
}) {
  const shown = value ?? fallback;
  const [raw, setRaw] = useState<string | null>(null);
  const text = raw ?? (shown == null ? "" : String(shown));
  const n = Number(text.replace(",", "."));
  const invalid = text !== "" && (Number.isNaN(n) || n < MIN_HOURS || n > MAX_HOURS);
  return (
    <Field
      label={label}
      htmlFor={id}
      hint={hint ?? `Entre ${String(MIN_HOURS).replace(".", ",")} e ${MAX_HOURS} horas`}
      error={invalid ? `Use um valor entre ${String(MIN_HOURS).replace(".", ",")} e ${MAX_HOURS}` : undefined}
    >
      <Input
        id={id}
        inputMode="decimal"
        value={text}
        aria-invalid={invalid || undefined}
        onChange={(e) => {
          setRaw(e.target.value);
          const v = Number(e.target.value.replace(",", "."));
          if (e.target.value.trim() === "") onChange(undefined);
          else if (!Number.isNaN(v)) onChange(v);
        }}
        onBlur={() => setRaw(null)}
        className="max-w-[7rem]"
      />
    </Field>
  );
}

/** Textarea com chips de variáveis que inserem `{{x}}` na posição do cursor. */
function TextWithVars({
  id,
  label,
  value,
  limit,
  vars,
  placeholder,
  rows = 5,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  limit: number;
  vars: string[];
  placeholder?: string;
  rows?: number;
  onChange: (v: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const insert = (name: string) => {
    const el = ref.current;
    const token = `{{${name}}}`;
    const at = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? at;
    const next = value.slice(0, at) + token + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(at + token.length, at + token.length);
    });
  };
  return (
    <Field label={label} htmlFor={id}>
      <Textarea
        id={id}
        ref={ref}
        rows={rows}
        value={value}
        aria-invalid={byteLength(value) > limit || undefined}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <ByteCounter text={value} limit={limit} />
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-fg-3">Variáveis</span>
        {["username", ...vars].map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => insert(v)}
            className="rounded-sm border border-line px-1.5 py-0.5 font-mono text-xs text-fg-2 transition-colors duration-150 ease-out hover:border-line-strong hover:text-fg"
          >
            {`{{${v}}}`}
          </button>
        ))}
      </div>
    </Field>
  );
}

type OptionsMode = "none" | "links" | "replies";

function MessageFields({ node, graph, patch }: { node: MessageNode; graph: FlowGraph; patch: Patch }) {
  const vars = variablesOf(graph);
  const buttons = node.buttons ?? [];
  const replies = node.quick_replies ?? [];
  // Escolha do seletor guardada por nó: "links" sem botões ainda continua em "links".
  const [chosen, setChosen] = useState<{ id: string; mode: OptionsMode } | null>(null);
  const derived: OptionsMode = buttons.length ? "links" : replies.length ? "replies" : "none";
  const mode = chosen?.id === node.id ? chosen.mode : derived;

  const setMode = (m: OptionsMode) => {
    setChosen({ id: node.id, mode: m });
    // Botões de link e respostas rápidas não convivem: trocar descarta o outro lado.
    if (m === "none") patch({ buttons: [], quick_replies: [] } as Partial<GraphNode>);
    if (m === "links") patch({ quick_replies: [], timeout_hours: undefined } as Partial<GraphNode>);
    if (m === "replies") patch({ buttons: [] } as Partial<GraphNode>);
  };

  const setButton = (i: number, b: Partial<{ label: string; url: string }>) =>
    patch({ buttons: buttons.map((x, j) => (j === i ? { ...x, ...b } : x)) } as Partial<GraphNode>, `btn-${node.id}-${i}`);
  const setReply = (i: number, title: string) =>
    patch({ quick_replies: replies.map((q, j) => (j === i ? { ...q, title } : q)) } as Partial<GraphNode>, `qr-${node.id}-${i}`);
  const moveReply = (i: number, dir: -1 | 1) => {
    const next = [...replies];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    patch({ quick_replies: next } as Partial<GraphNode>);
  };

  return (
    <>
      <TextWithVars
        id="node-text"
        label="Texto"
        value={node.text ?? ""}
        limit={textLimit(node)}
        vars={vars}
        placeholder="Oi {{username}}, obrigado pelo contato"
        onChange={(v) => patch({ text: v } as Partial<GraphNode>, `text-${node.id}`)}
      />

      <div>
        <p className="mb-2 text-[13px] font-medium text-fg-2">Opções abaixo da mensagem</p>
        <Segmented<OptionsMode>
          aria-label="Opções abaixo da mensagem"
          value={mode}
          onChange={setMode}
          options={[
            { value: "none", label: "Nenhuma" },
            { value: "links", label: "Links" },
            { value: "replies", label: "Respostas" },
          ]}
        />
      </div>

      {mode === "links" && (
        <div>
          <div className="space-y-2">
            {buttons.map((b, i) => (
              <div key={i}>
                <div className="flex items-center gap-2">
                  <Input
                    aria-label={`Rótulo do botão ${i + 1}`}
                    value={b.label}
                    onChange={(e) => setButton(i, { label: e.target.value })}
                    placeholder="Acessar oferta"
                  />
                  <Input
                    aria-label={`URL do botão ${i + 1}`}
                    aria-invalid={(!!b.url.trim() && !isUrl(b.url)) || undefined}
                    value={b.url}
                    onChange={(e) => setButton(i, { url: e.target.value })}
                    placeholder="https://"
                  />
                  <IconButton
                    icon={X}
                    aria-label={`Remover botão ${i + 1}`}
                    onClick={() => patch({ buttons: buttons.filter((_, j) => j !== i) } as Partial<GraphNode>)}
                  />
                </div>
                {!!b.url.trim() && !isUrl(b.url) && (
                  <p className="mt-1.5 text-xs text-negative">A URL precisa começar com http:// ou https://</p>
                )}
              </div>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={Plus}
            className="-ml-3 mt-2"
            disabled={buttons.length >= MAX_BUTTONS}
            onClick={() => patch({ buttons: [...buttons, { label: "", url: "" }] } as Partial<GraphNode>)}
          >
            Adicionar botão
          </Button>
        </div>
      )}

      {mode === "replies" && (
        <div className="space-y-3">
          <div className="space-y-2">
            {replies.map((q, i) => (
              <div key={q.id} className="flex items-center gap-1">
                <div className="relative flex-1">
                  <Input
                    aria-label={`Título da resposta rápida ${i + 1}`}
                    value={q.title}
                    aria-invalid={q.title.length > QUICK_REPLY_TITLE_MAX || undefined}
                    onChange={(e) => setReply(i, e.target.value)}
                    placeholder={`Opção ${i + 1}`}
                    className="pr-14"
                  />
                  <span
                    className={cx(
                      "pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 font-mono text-xs tabular-nums",
                      q.title.length > QUICK_REPLY_TITLE_MAX ? "text-negative" : "text-fg-3"
                    )}
                  >
                    {q.title.length}/{QUICK_REPLY_TITLE_MAX}
                  </span>
                </div>
                <IconButton icon={ArrowUp} aria-label={`Subir resposta ${i + 1}`} disabled={i === 0} onClick={() => moveReply(i, -1)} />
                <IconButton icon={ArrowDown} aria-label={`Descer resposta ${i + 1}`} disabled={i === replies.length - 1} onClick={() => moveReply(i, 1)} />
                <IconButton
                  icon={X}
                  aria-label={`Remover resposta ${i + 1}`}
                  onClick={() => patch({ quick_replies: replies.filter((_, j) => j !== i) } as Partial<GraphNode>)}
                />
              </div>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={Plus}
            className="-ml-3"
            disabled={replies.length >= MAX_QUICK_REPLIES}
            onClick={() =>
              patch({ quick_replies: [...replies, { id: newItemId("q"), title: "" }] } as Partial<GraphNode>)
            }
          >
            Adicionar resposta ({replies.length}/{MAX_QUICK_REPLIES})
          </Button>
          <HoursField
            id="node-timeout"
            label="Esperar resposta por (horas)"
            value={node.timeout_hours}
            fallback={23}
            onChange={(n) => patch({ timeout_hours: n } as Partial<GraphNode>, `to-${node.id}`)}
            hint="Depois desse prazo o fluxo segue por “Sem resposta”. No máximo 23 h: a janela de 24 h da Meta fecha"
          />
          <Note>
            Respostas rápidas não aparecem no Instagram desktop, só no aplicativo do celular
          </Note>
        </div>
      )}
    </>
  );
}

export default function NodeInspector({
  node,
  graph,
  isStart,
  triggerLabel,
  patch,
  onDelete,
}: {
  /** `null` = nenhum nó selecionado; "trigger" = o Gatilho. */
  node: GraphNode | "trigger" | null;
  graph: FlowGraph;
  isStart: boolean;
  triggerLabel: string;
  patch: Patch;
  onDelete: () => void;
}) {
  if (node === null) {
    return <p className="px-1 py-6 text-center text-[13px] text-fg-3">Selecione um nó para editar</p>;
  }
  if (node === "trigger") {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-fg">Gatilho</h3>
        <p className="text-[13px] text-fg-2">{triggerLabel}</p>
        <Note>
          O gatilho é configurado no card acima. A ligação dele define o primeiro nó do fluxo e não
          pode ser apagada; para trocar o primeiro nó, ligue o gatilho a outro nó
        </Note>
      </div>
    );
  }

  const vars = variablesOf(graph);
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-fg">{NODE_LABEL[node.type]}</h3>

      {node.type === "message" && <MessageFields node={node} graph={graph} patch={patch} />}

      {node.type === "question" && (
        <>
          <TextWithVars
            id="node-text"
            label="Pergunta"
            value={node.text ?? ""}
            limit={1000}
            vars={vars.filter((v) => v !== node.save_as)}
            placeholder="Qual é o seu e-mail?"
            rows={4}
            onChange={(v) => patch({ text: v } as Partial<GraphNode>, `text-${node.id}`)}
          />
          <Field
            label="Salvar resposta como"
            htmlFor="node-save-as"
            hint="Use depois como {{nome}} nas mensagens"
            error={node.save_as && !VAR_RE.test(node.save_as) ? "Use letras minúsculas, números e _; comece com letra" : undefined}
          >
            <Input
              id="node-save-as"
              value={node.save_as ?? ""}
              onChange={(e) => patch({ save_as: e.target.value } as Partial<GraphNode>, `sv-${node.id}`)}
              placeholder="email"
              className="font-mono"
            />
          </Field>
          <HoursField
            id="node-timeout"
            label="Esperar resposta por (horas)"
            value={node.timeout_hours}
            fallback={23}
            onChange={(n) => patch({ timeout_hours: n } as Partial<GraphNode>, `to-${node.id}`)}
            hint="Depois desse prazo o fluxo segue por “Sem resposta”. No máximo 23 h"
          />
        </>
      )}

      {node.type === "condition" && (
        <>
          <Field label="Verificar" htmlFor="node-mode">
            <Select
              id="node-mode"
              value={node.mode ?? "text_contains"}
              onChange={(e) => patch({ mode: e.target.value as ConditionMode } as Partial<GraphNode>)}
            >
              {(Object.keys(CONDITION_LABEL) as ConditionMode[]).map((m) => (
                <option key={m} value={m}>
                  {CONDITION_LABEL[m]}
                </option>
              ))}
            </Select>
          </Field>
          {(node.mode === "var_contains" || node.mode === "var_exists") && (
            <Field label="Variável" htmlFor="node-var" hint={vars.length ? undefined : "Crie uma Pergunta para ter variáveis"}>
              <Select
                id="node-var"
                value={node.var ?? ""}
                onChange={(e) => patch({ var: e.target.value } as Partial<GraphNode>)}
              >
                <option value="">Escolha…</option>
                {[...vars, ...(node.var && !vars.includes(node.var) ? [node.var] : [])].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          {(node.mode === "text_contains" || node.mode === "var_contains" || !node.mode) && (
            <Field
              label="Valor"
              htmlFor="node-value"
              hint={
                node.mode === "var_contains"
                  ? "Sem diferenciar maiúsculas de minúsculas"
                  : "O texto que disparou o fluxo ou a última resposta, sem diferenciar maiúsculas"
              }
            >
              <Input
                id="node-value"
                value={node.value ?? ""}
                onChange={(e) => patch({ value: e.target.value } as Partial<GraphNode>, `val-${node.id}`)}
                placeholder={node.mode === "var_contains" ? "@" : "preço"}
              />
            </Field>
          )}
        </>
      )}

      {node.type === "image" && (
        <>
          <Field label="URL da imagem" htmlFor="node-url" error={node.url && !isUrl(node.url) ? "A URL precisa começar com http:// ou https://" : undefined}>
            <Input
              id="node-url"
              value={node.url ?? ""}
              onChange={(e) => patch({ url: e.target.value } as Partial<GraphNode>, `url-${node.id}`)}
              placeholder="https://"
            />
          </Field>
          {node.url && isUrl(node.url) && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={node.url.trim()}
              alt="Prévia da imagem"
              className="max-h-40 rounded-control border border-line object-contain"
              onError={(e) => (e.currentTarget.style.display = "none")}
              onLoad={(e) => (e.currentTarget.style.display = "")}
            />
          )}
          <Note>PNG ou JPEG, até 8 MB. A Meta aceita só imagens por URL pública</Note>
        </>
      )}

      {node.type === "delay" && (
        <>
          <HoursField
            id="node-hours"
            label="Esperar (horas)"
            value={node.hours}
            onChange={(n) => patch({ hours: n } as Partial<GraphNode>, `h-${node.id}`)}
          />
          <Note variant="warning">
            A mensagem seguinte só sai se a janela de 24 h ainda estiver aberta
            {node.hours != null ? ` (esperar ${formatHours(node.hours)})` : ""}
          </Note>
        </>
      )}

      <div className="border-t border-line pt-4">
        <Button variant="danger" size="sm" icon={Trash2} onClick={onDelete} className="-ml-3">
          Excluir nó
        </Button>
        {isStart && (
          <p className="mt-2 text-xs text-fg-3">É o primeiro nó. Para excluir, ele precisa ter um nó logo depois</p>
        )}
      </div>
    </div>
  );
}
