"use client";

import { CircleAlert, CircleCheck, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Button from "./Button";
import IconButton from "./IconButton";
import { cx } from "./cx";

type Tone = "default" | "error";
type ToastItem = { id: number; message: string; tone: Tone };

type ConfirmOptions = {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** "danger" pinta a ação de confirmar como destrutiva. */
  tone?: "default" | "danger";
};

type Feedback = {
  toast: (message: string, tone?: Tone) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
};

const Ctx = createContext<Feedback | null>(null);

export function useFeedback(): Feedback {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFeedback precisa de <FeedbackProvider>");
  return ctx;
}

const TOAST_MS = { default: 4000, error: 6000 } as const;

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, tone: Tone = "default") => {
      const id = nextId.current++;
      // Máximo de 3 na tela: o mais antigo sai.
      setToasts((t) => [...t.slice(-2), { id, message, tone }]);
      window.setTimeout(() => dismiss(id), TOAST_MS[tone]);
    },
    [dismiss]
  );

  // ── Confirmação ──
  const [dialog, setDialog] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((ok: boolean) => void) | null>(null);
  const ref = useRef<HTMLDialogElement>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      resolver.current?.(false);
      resolver.current = resolve;
      setDialog(options);
    });
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (dialog && el && !el.open) el.showModal();
  }, [dialog]);

  function settle(ok: boolean) {
    ref.current?.close();
    resolver.current?.(ok);
    resolver.current = null;
    setDialog(null);
  }

  const value = useMemo(() => ({ toast, confirm }), [toast, confirm]);

  return (
    <Ctx.Provider value={value}>
      {children}

      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2"
      >
        {toasts.map((t) => {
          const Icon = t.tone === "error" ? CircleAlert : CircleCheck;
          return (
            <div
              key={t.id}
              role="status"
              className="toast-in pointer-events-auto flex items-start gap-2.5 rounded-card border border-line-strong bg-raised p-3 pr-2 shadow-[0_8px_24px_rgba(0,0,0,0.4)]"
            >
              <Icon
                size={16}
                strokeWidth={1.5}
                className={cx("mt-0.5 shrink-0", t.tone === "error" ? "text-negative" : "text-positive")}
              />
              <p className="min-w-0 flex-1 text-[13px] leading-5 text-fg">{t.message}</p>
              <IconButton
                icon={X}
                aria-label="Fechar aviso"
                onClick={() => dismiss(t.id)}
                className="-my-1"
              />
            </div>
          );
        })}
      </div>

      <dialog
        ref={ref}
        // Esc e clique fora cancelam; o `close` nativo cobre os dois.
        onCancel={(e) => {
          e.preventDefault();
          settle(false);
        }}
        onClick={(e) => {
          if (e.target === ref.current) settle(false);
        }}
        aria-labelledby="confirm-title"
        className="m-auto w-[min(400px,calc(100vw-2rem))] rounded-panel border border-line-strong bg-card p-0 text-fg backdrop:bg-black/60"
      >
        {dialog && (
          <div className="p-6">
            <h2 id="confirm-title" className="text-base font-medium text-fg">
              {dialog.title}
            </h2>
            {dialog.description && (
              <p className="mt-2 text-[13px] leading-5 text-fg-2">{dialog.description}</p>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => settle(false)} autoFocus>
                {dialog.cancelLabel ?? "Cancelar"}
              </Button>
              <Button
                variant={dialog.tone === "danger" ? "danger" : "primary"}
                size="sm"
                className={dialog.tone === "danger" ? "border border-negative/30" : undefined}
                onClick={() => settle(true)}
              >
                {dialog.confirmLabel ?? "Confirmar"}
              </Button>
            </div>
          </div>
        )}
      </dialog>
    </Ctx.Provider>
  );
}
