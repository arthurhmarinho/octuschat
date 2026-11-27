"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { MIN_PASSWORD } from "@/components/PasswordForm";
import { Field, IconButton, Input } from "@/components/ui";

export const passwordReady = (password: string, confirm: string) =>
  password.length >= MIN_PASSWORD && confirm === password;

/** "Senha" + "Confirmar senha" de quem ainda não tem uma (cadastro e redefinição). */
export default function NewPasswordFields({
  label = "Senha",
  password,
  confirm,
  onPassword,
  onConfirm,
}: {
  label?: string;
  password: string;
  confirm: string;
  onPassword: (v: string) => void;
  onConfirm: (v: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const mismatch = confirm.length > 0 && confirm !== password;
  const type = visible ? "text" : "password";

  return (
    <>
      <Field
        label={label}
        htmlFor="new-password"
        hint={`Pelo menos ${MIN_PASSWORD} caracteres`}
        error={tooShort ? `Pelo menos ${MIN_PASSWORD} caracteres` : undefined}
      >
        <div className="relative">
          <Input
            id="new-password"
            type={type}
            autoComplete="new-password"
            value={password}
            onChange={(e) => onPassword(e.target.value)}
            className="pr-10"
          />
          <IconButton
            icon={visible ? EyeOff : Eye}
            aria-label={visible ? "Ocultar senha" : "Mostrar senha"}
            aria-pressed={visible}
            onClick={() => setVisible((v) => !v)}
            className="absolute right-1 top-1/2 -translate-y-1/2"
          />
        </div>
      </Field>
      <Field
        label="Confirmar senha"
        htmlFor="confirm-password"
        error={mismatch ? "As senhas não são iguais" : undefined}
      >
        <Input
          id="confirm-password"
          type={type}
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => onConfirm(e.target.value)}
        />
      </Field>
    </>
  );
}
