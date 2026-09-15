"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowCounterClockwise, ClockCounterClockwise, FileText, Gear } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import IconButton from "@/components/ui/IconButton";
import { useGlossaries } from "@/hooks/useGlossaries";
import ConversationView from "./_components/ConversationView";
import ProtocolModal from "./_components/ProtocolModal";
import SavedConversationsModal from "./_components/SavedConversationsModal";
import SettingsModal from "./_components/SettingsModal";
import { createSession, deleteSession, fetchSession, listSessions, patchSession, putTurn, type Glossary, type SessionSummary } from "./_api";
import { createMirror } from "./_mirror";
import { useConversation } from "./_hooks/useConversation";
import { useInterpreterConfig } from "./_hooks/useInterpreterConfig";
import { otherLang, otherSide, type LangCode, type LanguageOption, type Side, type Turn } from "./_types";

const ACTION = "px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap";

export default function InterpreterPage() {
  const t = useTranslations("tools.interpreter");
  const locale = useLocale();

  const fallbackLanguages = useMemo<LanguageOption[]>(
    () => [{ id: "DE", label: t("languages.de") }, { id: "EN-US", label: t("languages.en") }],
    [t],
  );
  const { translationProviders, sttProviders } = useInterpreterConfig(fallbackLanguages);

  const [langs, setLangs] = useState<Record<Side, LangCode>>({ left: "DE", right: "EN-US" });
  const [names, setNames] = useState<Record<Side, string>>(() => ({ left: t("speaker.defaultLeft"), right: t("speaker.defaultRight") }));
  const langsRef = useRef(langs);
  langsRef.current = langs;
  const namesRef = useRef(names);
  namesRef.current = names;
  const [sttProviderId, setSttProviderId] = useState<number | null>(null);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
  const [glossaryIds, setGlossaryIds] = useState<string[]>([]);
  const [protocolOpen, setProtocolOpen] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saved, setSaved] = useState<SessionSummary[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const { mergeToApiJson } = useGlossaries();
  const glossaryJson = mergeToApiJson(glossaryIds);
  const glossary = useMemo<Glossary>(() => {
    try {
      return glossaryJson ? (JSON.parse(glossaryJson) as Record<string, string>) : null;
    } catch {
      return null;
    }
  }, [glossaryJson]);

  // The stand-in list is replaced once the real providers arrive, the choice follows.
  useEffect(() => {
    if (sttProviders.length && !sttProviders.some((p) => p.id === sttProviderId)) setSttProviderId(sttProviders[0].id);
  }, [sttProviders, sttProviderId]);
  useEffect(() => {
    if (translationProviders.length && !translationProviders.some((p) => p.id === translationProviderId)) {
      setTranslationProviderId(translationProviders[0].id);
    }
  }, [translationProviders, translationProviderId]);

  // --- the conversation of two people lives on the server --------------------------------------

  const [sessionId, setSessionId] = useState<string | null>(null);
  const running = useRef<string | null>(null);
  const creating = useRef<Promise<string> | null>(null);

  const adopt = useCallback((id: string | null) => {
    running.current = id;
    setSessionId(id);
  }, []);

  /** The server row appears with the first sentence. */
  const ensureSession = useCallback(async (): Promise<string> => {
    if (running.current) return running.current;
    if (!creating.current) {
      creating.current = createSession({
        left_lang: langsRef.current.left,
        right_lang: langsRef.current.right,
        left_name: namesRef.current.left,
        right_name: namesRef.current.right,
      })
        .then((state) => {
          adopt(state.id);
          return state.id;
        })
        .finally(() => {
          creating.current = null;
        });
    }
    return creating.current;
  }, [adopt]);

  const mirror = useMemo(() => createMirror(async (turn: Turn) => putTurn(await ensureSession(), turn)), [ensureSession]);
  const onTurn = useCallback((turn: Turn) => mirror.push(turn), [mirror]);

  const langOf = useCallback((side: Side) => langsRef.current[side], []);
  const active = useConversation({ langOf, providerId: translationProviderId, sttProviderId, glossary, onTurn });

  // --- what the buttons do --------------------------------------------------------------------

  const formatTime = useCallback(
    (at: number) => new Date(at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }),
    [locale],
  );
  const formatDate = useCallback(
    (iso: string) => new Date(iso).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }),
    [locale],
  );

  const allowSetup = active.turns.length === 0;

  const patchIfRunning = useCallback((meta: Parameters<typeof patchSession>[1]) => {
    if (running.current) void patchSession(running.current, meta).catch(() => {});
  }, []);

  const rename = (side: Side, name: string) => {
    setNames((cur) => ({ ...cur, [side]: name }));
    patchIfRunning(side === "left" ? { left_name: name } : { right_name: name });
  };

  // Only two languages, so a change on one side decides the other side too.
  const changeLanguage = (side: Side, code: LangCode) => {
    if (!allowSetup || langs[side] === code) return;
    const next = { left: side === "left" ? code : otherLang(code), right: side === "right" ? code : otherLang(code) };
    setLangs(next);
    active.flipTexts();
    patchIfRunning({ left_lang: next.left, right_lang: next.right });
  };

  const swap = () => {
    if (!allowSetup) return;
    const nextLangs = { left: langs.right, right: langs.left };
    const nextNames = { left: names.right, right: names.left };
    setLangs(nextLangs);
    setNames(nextNames);
    active.flipSides();
    patchIfRunning({ left_lang: nextLangs.left, right_lang: nextLangs.right, left_name: nextNames.left, right_name: nextNames.right });
  };

  const newConversation = useCallback(() => {
    active.reset();
    mirror.cancel();
    adopt(null);
  }, [adopt, active, mirror]);

  const openSavedList = () => {
    setSavedOpen(true);
    setSavedLoading(true);
    listSessions()
      .then(setSaved)
      .catch(() => setSaved([]))
      .finally(() => setSavedLoading(false));
  };

  const openSaved = async (entry: SessionSummary) => {
    try {
      const state = await fetchSession(entry.id);
      mirror.cancel();
      adopt(state.id);
      active.load(state.turns, state.ended);
      setLangs({ left: state.left_lang, right: state.right_lang });
      setNames({ left: state.left_name || namesRef.current.left, right: state.right_name || namesRef.current.right });
      setSavedOpen(false);
    } catch {
      // The list stays open, the entry could not be loaded.
    }
  };

  const deleteSaved = async (id: string) => {
    try {
      await deleteSession(id);
      setSaved((list) => list.filter((entry) => entry.id !== id));
      if (running.current === id) newConversation();
    } catch {
      // Nothing to do, the entry stays.
    }
  };

  return (
    <ProtectedRoute>
      <div className="max-w-5xl mx-auto px-4 py-8">
        <ToolBackLink />
        <section data-tour="tool-interpreter">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <h1 className="text-xl font-bold">{t("title")}</h1>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => setProtocolOpen(true)} className={ACTION}>
                <FileText size={14} weight="bold" />
                {t("actions.protocol")}
              </button>
              <button type="button" onClick={openSavedList} className={ACTION}>
                <ClockCounterClockwise size={14} weight="bold" />
                {t("actions.saved")}
              </button>
              <button type="button" onClick={newConversation} className={ACTION}>
                <ArrowCounterClockwise size={14} weight="bold" />
                {t("actions.newConversation")}
              </button>
              <IconButton onClick={() => setSettingsOpen(true)} aria-label={t("actions.settings")} title={t("actions.settings")}>
                <Gear size={16} weight="bold" />
              </IconButton>
            </div>
          </div>
          <p className="text-sm text-muted mb-1">{t("intro")}</p>
          <p className="text-sm text-muted mb-5">{t("hint")}</p>

          <ConversationView
            turns={active.turns}
            recording={active.recording}
            quiet={active.quiet}
            floor={active.floor}
            ended={active.ended}
            notice={active.notice}
            langs={langs}
            names={names}
            allowSetup={allowSetup}
            onLanguage={changeLanguage}
            onRename={rename}
            onSwap={swap}
            onMic={active.toggleMic}
            onBegin={active.begin}
            onType={active.type}
            onTranslate={active.translateTyped}
            formatTime={formatTime}
          />
        </section>
      </div>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        sttProviders={sttProviders}
        sttProviderId={sttProviderId}
        onStt={setSttProviderId}
        translationProviders={translationProviders}
        translationProviderId={translationProviderId}
        onTranslation={setTranslationProviderId}
        glossaryIds={glossaryIds}
        onGlossary={setGlossaryIds}
      />
      <ProtocolModal open={protocolOpen} onClose={() => setProtocolOpen(false)} turns={active.turns} names={names} formatTime={formatTime} />
      <SavedConversationsModal
        open={savedOpen}
        onClose={() => setSavedOpen(false)}
        list={saved}
        loading={savedLoading}
        currentId={sessionId}
        onOpen={(entry) => void openSaved(entry)}
        onDelete={(id) => void deleteSaved(id)}
        formatDate={formatDate}
      />
    </ProtectedRoute>
  );
}
