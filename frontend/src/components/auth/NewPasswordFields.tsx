"use client";

/** New password with show/hide and its repetition, shared by invitation and reset page. */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeSlash } from "@phosphor-icons/react";
import { MIN_PASSWORD_LENGTH } from "@/app/[locale]/invite/[token]/checkPassword";
import { AUTH_FIELD } from "./authField";

type Props = {
  namespace: "invite" | "resetPassword";
  idPrefix: string;
  password: string;
  repeat: string;
  onPassword: (value: string) => void;
  onRepeat: (value: string) => void;
  disabled: boolean;
};

export default function NewPasswordFields({
  namespace, idPrefix, password, repeat, onPassword, onRepeat, disabled,
}: Props) {
  const t = useTranslations(namespace);
  const [showPassword, setShowPassword] = useState(false);

  return (
    <>
      <div>
        <label htmlFor={`${idPrefix}-password`} className="block text-sm font-medium text-foreground-soft mb-1.5">
          {t("password")}
        </label>
        <div className="relative">
          <input
            id={`${idPrefix}-password`}
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => onPassword(e.target.value)}
            autoComplete="new-password"
            required
            disabled={disabled}
            className={`${AUTH_FIELD} pr-11`}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? t("hidePassword") : t("showPassword")}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-muted hover:text-kb transition-colors"
            tabIndex={-1}
          >
            {showPassword ? <EyeSlash size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
          </button>
        </div>
        <p className="mt-1.5 text-xs text-muted-soft">{t("passwordHint", { min: MIN_PASSWORD_LENGTH })}</p>
      </div>

      <div>
        <label htmlFor={`${idPrefix}-password-repeat`} className="block text-sm font-medium text-foreground-soft mb-1.5">
          {t("passwordRepeat")}
        </label>
        <input
          id={`${idPrefix}-password-repeat`}
          type={showPassword ? "text" : "password"}
          value={repeat}
          onChange={(e) => onRepeat(e.target.value)}
          autoComplete="new-password"
          required
          disabled={disabled}
          className={AUTH_FIELD}
        />
      </div>
    </>
  );
}
