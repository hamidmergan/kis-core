"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useParams, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Lock } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { Link } from "@/i18n/navigation";

import type {
  WorkspaceDetail,
  ViewerState,
  StudioView,
  LanguageTrainingView,
  StaffNoteLink,
} from "./_types";
import { _isMediaFile } from "./_utils";
import { NOTE_BODY_MAX } from "./_constants";
import { usePanelLayout } from "./_hooks/usePanelLayout";
import { useSources } from "./_hooks/useSources";
import { useChapters } from "./_hooks/useChapters";
import { useMindmap } from "./_hooks/useMindmap";
import { useDataTable } from "./_hooks/useDataTable";
import { useNotes } from "./_hooks/useNotes";
import { useExercises } from "./_hooks/useExercises";
import { useLanguageTraining } from "./_hooks/useLanguageTraining";
import { useChat } from "./_hooks/useChat";
import { useStats } from "./_hooks/useStats";
import { useViewerActions } from "./_hooks/useViewerActions";
import { useWorkspaceInit } from "./_hooks/useWorkspaceInit";
import { useStudioNavigation } from "./_hooks/useStudioNavigation";

// Lightweight components needed on initial render
import { SourcesPanel } from "./_components/sources/SourcesPanel";
import { ChatPanel } from "./_components/chat/ChatPanel";
import { CreateSetModal } from "./_components/language_training/CreateSetModal";
import { GlossaryView } from "./_components/language_training/GlossaryView";
import { LanguageDiagnosisPanel } from "./_components/language_training/LanguageDiagnosisPanel";
import { WorkspaceTopbar } from "./_components/layout/WorkspaceTopbar";
import { OwnerPreviewProvider } from "./_components/layout/OwnerOnly";
import { resolvePreview } from "./_preview";
import { useTour } from "./_tour/useTour";
import type { TourAktionen } from "./_tour/demoSteps";
import { WorkspacePanelsLayout } from "./_components/layout/WorkspacePanelsLayout";
import { StudioPanelContent } from "./_components/studio/StudioPanelContent";
import { LanguageTrainingContent } from "./_components/language_training/LanguageTrainingContent";

// Heavy / conditionally-rendered components: loaded on demand to keep initial bundle small
const dynamicLoader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const PdfViewer = dynamic(() => import("./_components/viewer/PdfViewer").then((m) => ({ default: m.PdfViewer })), { loading: dynamicLoader, ssr: false });
const MediaPlayer = dynamic(() => import("./_components/viewer/MediaPlayer").then((m) => ({ default: m.MediaPlayer })), { loading: dynamicLoader, ssr: false });
const NotesStudio = dynamic(() => import("./_components/studio/NotesStudio").then((m) => ({ default: m.NotesStudio })), { loading: dynamicLoader, ssr: false });


// ─── Page ──────────────────────────────────────────────────────────────────────

export default function KiTutorWorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const tClosed = useTranslations("workspace.detail.closed");
  const uuid = params.uuid as string;
  const enrollmentId = searchParams.get("eid") ? Number(searchParams.get("eid")) : null;
  const initialTab = searchParams.get("tab");

  const [moduleDetail, setWorkspaceDetail] = useState<WorkspaceDetail | null>(null);
  // auth + initialized come from useWorkspaceInit (after all source/chat hooks)

  // Comes after viewerSource because the hook needs it as input.

  const {
    sources, setSources,
    selectedSourceIds, setSelectedSourceIds,
    uploadProgress,
    uploadErrors, setUploadErrors,
    toggleSource: handleToggleSource,
    deleteSource: handleDeleteSource,
    renameSource: handleRenameSource,
    retrySource: handleRetrySource,
    uploadFiles: handleUpload,
  } = useSources({ uuid, onModuleUpdate: (mod) => setWorkspaceDetail(mod) });

  // Chapters only structure the list, the selection stays the file's checkbox.
  const {
    chapters, setChapters,
    closedChapters, toggleChapterOpen, openChapter,
    createChapter: handleCreateChapter,
    renameChapter: handleRenameChapter,
    deleteChapter: handleDeleteChapter,
    moveChapter: handleMoveChapter,
    setSourceChapter: handleSetSourceChapter,
  } = useChapters({ uuid, setSources });

  // The course room is the one truth, the structure comes along every time.
  useEffect(() => {
    if (moduleDetail?.chapters) setChapters(moduleDetail.chapters);
  }, [moduleDetail?.chapters, setChapters]);

  const [viewerSource, setViewerSource] = useState<ViewerState | null>(null);

  const {
    panels, setPanels,
    p1Width, p2Width, p3Width,
    activeTab, setActiveTab,
    isMobile,
    panelContainerRef, p1Ref, p2Ref, p3Ref,
    togglePanel, startDrag,
  } = usePanelLayout({ uuid, viewerSource });

  const [chatLang, setChatLang] = useState<"de" | "en">("de");
  // Target language of the selection bar translation, per reading person.
  const [popupTranslateLang, setPopupTranslateLang] = useState<string>("en");

  const chat = useChat({ uuid, enrollmentId, selectedSourceIds, viewerSource, chatLang, popupTranslateLang });
  const {
    messages, setMessages,
    chatLoading, popupActions,
    chatTextareaRef,
    registerChatSetInput,
    loadMessages, sendChatMessage, stopChat, retryLast,
    chatSetInputRef,
  } = chat;

  const [showSettings, setShowSettings] = useState(false);
  // null means nobody pressed the switch yet, then the default per course counts.
  const [previewOverride, setPreviewOverride] = useState<boolean | null>(null);
  const { start: startTour } = useTour();


  const [studioEnabled, setStudioEnabled] = useState(true);
  // The owner's decision for the whole course, the admin switch is already included.
  const [language_trainingActive, setLanguageTrainingActive] = useState(false);
  useEffect(() => {
    setLanguageTrainingActive(moduleDetail?.language_training_active ?? false);
  }, [moduleDetail?.language_training_active]);
  const languageTrainingAvailable = moduleDetail?.language_training_enabled ?? false;
  // The course releases it, each person switches it on, shown only when both are on.
  const [languageTrainingOptIn, setLanguageTrainingOptIn] = useState(false);
  const language_trainingVisible = language_trainingActive && languageTrainingOptIn;

  // The assessment starts when the trainer is on and no level is set yet.
  const [me, setMe] = useState<{ id: number; language_level: string | null } | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (!cancelled && data) setMe({ id: data.id, language_level: data.language_level }); })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, []);
  const diagnosisActive = language_trainingVisible && me !== null && me.language_level === null;
  // During the assessment only the rendering changes, the saved layout stays.
  const effectivePanels = diagnosisActive
    ? { quellen: false, chat: true, studio: false }
    : panels;

  const [transcriptTargetLang, setTranscriptTargetLang] = useState<string>("en");
  useEffect(() => {
    if (moduleDetail?.transcript_target_lang) {
      setTranscriptTargetLang(moduleDetail.transcript_target_lang);
    }
  }, [moduleDetail?.transcript_target_lang]);
  const handleChangeTranscriptTargetLang = (lang: string) => {
    setTranscriptTargetLang(lang);
    fetch(`/api/ai-assistant/workspaces/${uuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript_target_lang: lang }),
    }).catch(() => { /* ignore */ });
  };
  // The owner's switch, set locally up front and reverted on an error.
  const handleToggleLanguageTraining = () => {
    const next = !language_trainingActive;
    setLanguageTrainingActive(next);
    setWorkspaceDetail((prev) => (prev ? { ...prev, language_training_active: next } : prev));
    fetch(`/api/ai-assistant/workspaces/${uuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language_training_active: next }),
    })
      .then((res) => { if (!res.ok) throw new Error("save failed"); })
      .catch(() => {
        setLanguageTrainingActive(!next);
        setWorkspaceDetail((prev) => (prev ? { ...prev, language_training_active: !next } : prev));
      });
  };
  const handleStaffNoteSave = async (text: string | null, links: StaffNoteLink[]) => {
    const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ staff_note_text: text, staff_note_links: links }),
    });
    if (!res.ok) throw new Error("save failed");
    setWorkspaceDetail((prev) => (prev ? { ...prev, staff_note_text: text, staff_note_links: links } : prev));
  };
  // popupActions from useChat

  const [studioView, setStudioView] = useState<StudioView>("overview");
  const mm = useMindmap({ uuid, selectedSourceIds });
  const selectMindmap = mm.select;

  const dt = useDataTable({ uuid, selectedSourceIds });
  const selectDataTable = dt.select;
  const { notes, setNotes, pendingTitleIds, addNote, deleteNote, updateNoteTitle } = useNotes({ uuid });

  // A one-off tab wish, it has to be cleared or it pulls back on every mount.
  const [studioTabRequest, setStudioTabRequest] = useState<{ tab: "tools" | "glossary" | "notes" | "statistik" | "schedule"; nonce: number } | null>(null);
  const clearStudioTabRequest = useCallback(() => setStudioTabRequest(null), []);
  // Language training state: see useLanguageTraining (init after selectedSourceIds)

  // ─── Exercise sets state ─────────────────────────────────────────────────
  const ex = useExercises({ uuid });
  const {
    exerciseSets, activeSet, setActiveSet,
    createSetTool, setCreateSetTool, showCreateModal, setShowCreateModal,
    loadExerciseSets, loadExerciseSet, createExerciseSet, deleteExerciseSet, renameExerciseSet,
    retryExerciseSet, downloadExerciseSet, submitSingleAnswer,
  } = ex;
  // statsVersion and glossaryCount come from the hooks below.

  // Wer über die Einladung auf der Startseite kommt, landet direkt im Rundgang.
  // Auch hierher gereicht, denn ohne Einschreibung weist der erste Abruf unten
  // die Person ab, bevor der Rundgang ueberhaupt anlaeuft.
  const tourAngefordert = searchParams.get("tour") === "1";

  // ─── Init (see useWorkspaceInit) ─────────────────────────────────────────
  const { auth, initialized, locked } = useWorkspaceInit({
    uuid,
    tourAngefordert,
    setSources,
    setSelectedSourceIds,
    setWorkspaceDetail,
    setNotes,
    loadMessages,
    onSettingsLoaded: (s) => {
      setChatLang(s.chat_lang);
      setStudioEnabled(s.studio_enabled);
      setPopupTranslateLang(s.popup_translate_lang);
      setLanguageTrainingOptIn(s.language_training_active);
    },
  });

  const { statsVersion, loadStreak, bumpStats } = useStats({ uuid, initialized });

  // Der Rundgang im Demo-Modul bedient die Oberflaeche selbst, seine Griffe
  // stehen weiter unten und liegen deshalb in einem Ref.
  const tourAktionenRef = useRef<TourAktionen | null>(null);
  const istDemoModul = moduleDetail?.is_demo_workspace ?? false;
  const istDemoModulRef = useRef(istDemoModul);
  istDemoModulRef.current = istDemoModul;
  // Wer keine Module anlegen darf, bekommt weder die Lehrenden-Vorschau noch
  // die Stationen, die auf deren Knoepfe zeigen.
  const darfModuleAnlegen = auth?.permissions?.allow_workspace_create ?? false;
  const darfModuleAnlegenRef = useRef(darfModuleAnlegen);
  darfModuleAnlegenRef.current = darfModuleAnlegen;
  const starteRundgang = useCallback(() => {
    startTour({
      demo: istDemoModulRef.current,
      aktionen: tourAktionenRef.current ?? undefined,
      workspaceUuid: uuid,
      darfModuleAnlegen: darfModuleAnlegenRef.current,
    });
  }, [startTour, uuid]);

  const tourGestartet = useRef(false);
  useEffect(() => {
    if (!initialized || !tourAngefordert || tourGestartet.current) return;
    tourGestartet.current = true;
    // Die Panels brauchen einen Moment, sonst zeigt der erste Schritt ins Leere.
    const timer = window.setTimeout(() => {
      starteRundgang();
      // Marke erst jetzt aus der Adresse nehmen, sonst startet jedes Neuladen den
      // Rundgang erneut und ein frueherer Griff danach loescht den Start-Timer.
      const url = new URL(window.location.href);
      url.searchParams.delete("tour");
      window.history.replaceState({}, "", url.toString());
    }, 700);
    return () => window.clearTimeout(timer);
  }, [initialized, tourAngefordert, starteRundgang]);

  // Reset mobile tab if studio is disabled
  useEffect(() => {
    if (!studioEnabled && activeTab === "studio") setActiveTab("chat");
  }, [studioEnabled, activeTab]);

  // Jump from the calendar straight to the schedule, once via a ref.
  const tabDeepLinkHandledRef = useRef(false);
  useEffect(() => {
    if (tabDeepLinkHandledRef.current) return;
    if (!initialized || initialTab !== "schedule" || !studioEnabled) return;
    tabDeepLinkHandledRef.current = true;
    setStudioTabRequest({ tab: "schedule", nonce: Date.now() });
    if (isMobile) setActiveTab("studio");
    else setPanels((prev) => ({ ...prev, studio: true }));
    const url = new URL(window.location.href);
    url.searchParams.delete("tab");
    window.history.replaceState({}, "", url.toString());
  }, [initialized, initialTab, studioEnabled, isMobile, setActiveTab, setPanels]);

  // Persist settings to DB (only after init to avoid overwriting with defaults)
  useEffect(() => {
    if (!initialized) return;
    fetch(`/api/ai-assistant/workspaces/${uuid}/settings`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_lang: chatLang,
        studio_enabled: studioEnabled,
        popup_translate_lang: popupTranslateLang,
        language_training_active: languageTrainingOptIn,
      }),
    }).catch(() => { /* ignore */ });
  }, [chatLang, studioEnabled, popupTranslateLang, languageTrainingOptIn, initialized, uuid]);

  // ─── Viewer + chat input actions (see useViewerActions) ─────────────────
  const {
    openViewer: handleOpenViewer,
    closeViewer: handleCloseViewer,
    askWithSelection: handleAskWithSelection,
    askChat: handleAskChat,
    customQuestion: handleCustomQuestion,
    pillClick: handlePillClick,
  } = useViewerActions({
    sources,
    setViewerSource, setPanels, panels,
    isMobile, activeTab, setActiveTab,
    chatSetInputRef, chatTextareaRef, sendChatMessage,
  });

  // Wrapper: glossary extraction with UI navigation to the glossary tab
  async function handleAddToGlossary(text: string, sourceUuid: string, page: number) {
    setSprachView("overview");
    setStudioView("overview");
    setStudioTabRequest({ tab: "glossary", nonce: Date.now() });
    if (isMobile) setActiveTab("studio");
    else setPanels((prev) => ({ ...prev, studio: true }));
    await extractGlossary(text, sourceUuid, page);
  }

  // Saves the PDF selection as a note with a citation chip back to the spot.
  async function handleAddToNote(text: string, sourceUuid: string, page: number) {
    const citation = ` [Q1:${sourceUuid}, S. ${page}]`;
    const bodyBudget = NOTE_BODY_MAX - citation.length;
    const truncated = text.length > bodyBudget ? text.slice(0, bodyBudget - 1) + "…" : text;
    setSprachView("overview");
    setStudioView("overview");
    setStudioTabRequest({ tab: "notes", nonce: Date.now() });
    if (isMobile) setActiveTab("studio");
    else setPanels((prev) => ({ ...prev, studio: true }));
    await addNote(
      truncated + citation,
      [sourceUuid],
      { popupSelection: { uuid: sourceUuid, page, text: truncated } },
    );
  }

  // ─── Language training functions (from useLanguageTraining) ──────────────
  const spr = useLanguageTraining({ uuid });
  const {
    langTrainingView, setSprachView,
    glossary, glossaryCount, glossaryExtracting, glossaryFeedback,
    deleteGlossaryEntry, deleteAllGlossaryEntries,
    loadGlossary, loadGlossaryCount,
    extractGlossary, dismissFeedback,
  } = spr;

  // What the guided tour is allowed to do: open, tick, switch. It never sends.
  const quelleNachName = (dateiPraefix: string) =>
    sources.find((s) => s.filename.startsWith(dateiPraefix));
  tourAktionenRef.current = {
    nurWaehlen: (dateiPraefix) => {
      const quelle = quelleNachName(dateiPraefix);
      if (!quelle) return;
      // A row inside a folded chapter is not on the page, so its chapter opens first.
      if (quelle.chapter_uuid) openChapter(quelle.chapter_uuid);
      setSelectedSourceIds([quelle.uuid]);
    },
    oeffnen: (dateiPraefix) => {
      const quelle = quelleNachName(dateiPraefix);
      if (quelle) handleOpenViewer(quelle);
    },
    studioReiter: (reiter) => {
      setStudioView("overview");
      setStudioTabRequest({ tab: reiter, nonce: Date.now() });
      if (isMobile) setActiveTab("studio");
      else setPanels((prev) => ({ ...prev, studio: true }));
    },
    materialListe: () => {
      // The panel shows either the list or an opened viewer, the list needs both closed.
      handleCloseViewer();
      if (isMobile) setActiveTab("quellen");
      else setPanels((prev) => ({ ...prev, quellen: true }));
    },
    beispieleLaden: () => {
      void loadGlossary();
      void loadGlossaryCount();
      // Werkzeuge und Übungsverlauf entstehen ebenfalls erst nach dem Seitenaufbau.
      bumpStats();
      void loadStreak();
      fetch(`/api/ai-assistant/workspaces/${uuid}/notes`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : null))
        .then((frisch) => { if (frisch) setNotes(frisch); })
        .catch(() => { /* Ohne die Beispiele stehen die Bereiche eben leer da. */ });
    },
    chatBeispielZeigen: () => {
      // On narrow screens the studio still covers the chat from the step before.
      if (isMobile) setActiveTab("chat");
      else setPanels((prev) => ({ ...prev, chat: true }));
      fetch("/api/ai-assistant/demo/tour-chat-example", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_uuid: uuid }),
      })
        .then(() => loadMessages())
        .catch(() => { /* Ohne das Beispiel bleibt der Chat leer, das ist kein Fehler. */ });
    },
  };

  // Studio navigation (see useStudioNavigation)
  const {
    handleStudioSelect, handleNavigateToSet, handleSprachNavigate, refreshProgress,
    openMindmapInViewer, consumeMindmapViewerOpen,
    openDataTableInViewer, consumeDataTableViewerOpen,
  } = useStudioNavigation({
    studioView, setStudioView, setSprachView,
    loadExerciseSets, loadExerciseSet,
    selectMindmap, selectDataTable,
    loadStreak, bumpStats,
  });

  // All chosen sources, the same limit of 5 as for mind map and table.
  const setSourceUuids = selectedSourceIds.slice(0, 5);
  const selectedSourcesForSet = setSourceUuids
    .map((id) => sources.find((s) => s.uuid === id))
    .filter((s): s is NonNullable<typeof s> => Boolean(s))
    .map((s) => ({ uuid: s.uuid, filename: s.filename }));

  const isAdmin = auth?.is_admin ?? false;

  const language_trainingContent = (
    <LanguageTrainingContent
      langTrainingView={langTrainingView}
      setSprachView={setSprachView}
      exerciseSets={exerciseSets}
      activeSet={activeSet}
      setActiveSet={setActiveSet}
      loadExerciseSet={loadExerciseSet}
      loadExerciseSets={loadExerciseSets}
      deleteExerciseSet={deleteExerciseSet}
      renameExerciseSet={renameExerciseSet}
      retryExerciseSet={retryExerciseSet}
      downloadExerciseSet={downloadExerciseSet}
      setCreateSetTool={setCreateSetTool}
      setShowCreateModal={setShowCreateModal}
      submitSingleAnswer={submitSingleAnswer}
      selectedSourceIds={selectedSourceIds}
      workspaceUuid={uuid}
      isAdmin={isAdmin}
      sources={sources}
      refreshProgress={refreshProgress}
      handleAskChat={handleAskChat}
      handlePillClick={handlePillClick}
      chatLang={chatLang}
    />
  );

  const glossaryContent = (
    <GlossaryView
      entries={glossary}
      extracting={glossaryExtracting}
      onOpenSource={(filename, page, highlightText, startTime) => {
        const src = (filename && sources.find((s) => s.filename === filename))
          || sources.find((s) => selectedSourceIds.includes(s.uuid));
        if (!src) return;
        if (_isMediaFile(src.filename) && startTime != null) {
          // Do not narrow the selection, otherwise a single source sticks on reload.
          setViewerSource({ uuid: src.uuid, filename: src.filename, page: 0, startTime, nonce: Date.now() });
          setPanels((prev) => ({ ...prev, quellen: true }));
        } else {
          handleOpenViewer(src, page, highlightText, true);
        }
      }}
      onDelete={deleteGlossaryEntry}
      onDeleteAll={deleteAllGlossaryEntries}
      showTranslation={language_trainingVisible}
      feedback={glossaryFeedback}
      onDismissFeedback={dismissFeedback}
    />
  );

  const notesContent = (
    <NotesStudio
      notes={notes}
      onAdd={(content) => addNote(content, undefined, { autoTitle: false })}
      onDelete={deleteNote}
      onUpdateTitle={updateNoteTitle}
      sources={sources}
      activeSourceIds={selectedSourceIds}
      onPillClick={handlePillClick}
      pendingTitleIds={pendingTitleIds}
    />
  );

  // ─── Render ────────────────────────────────────────────────────────────────

  // The relationship to this course decides, never the role in the system.
  const { canPreview, previewOn, isOwner, ownerPreview, previewsOwnerSide } = resolvePreview({
    realIsOwner: moduleDetail?.can_manage ?? moduleDetail?.is_owner ?? false,
    isDemoWorkspace: moduleDetail?.is_demo_workspace ?? false,
    darfModuleAnlegen,
    override: previewOverride,
  });
  // An opened source does not switch the others off.
  const activeSourceIds = selectedSourceIds;

  const p1Style: React.CSSProperties = effectivePanels.quellen
    ? { flex: `1 1 ${p1Width}px`, minWidth: 200, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p2Style: React.CSSProperties = effectivePanels.chat
    ? { flex: `1 1 ${p2Width}px`, minWidth: 50, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p3Style: React.CSSProperties = effectivePanels.studio
    ? { flex: `1 1 ${p3Width}px`, minWidth: 200, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const openCount = [effectivePanels.quellen, effectivePanels.chat, effectivePanels.studio].filter(Boolean).length;
  const canDrag = openCount >= 2;

  // Studio panel content (mobile + desktop identical, only the panel context differs)
  const renderStudioPanel = (onMinimize: () => void, hideHeader = false) => (
    <div data-tour="studio-panel" className="h-full flex flex-col min-h-0">
    <StudioPanelContent
      studioView={studioView}
      setStudioView={setStudioView}
      langTrainingView={langTrainingView}
      language_trainingActive={language_trainingVisible}
      studioTabRequest={studioTabRequest}
      onStudioTabRequestHandled={clearStudioTabRequest}
      language_trainingContent={language_trainingContent}
      glossaryContent={glossaryContent}
      notesContent={notesContent}
      exercises={ex}
      notes={{ notes, addNote, deleteNote, updateNoteTitle, pendingTitleIds }}
      mindmap={mm}
      data_table={dt}
      workspaceUuid={uuid}
      statsVersion={statsVersion}
      sources={sources}
      selectedSourceIds={selectedSourceIds}
      isAdmin={isAdmin}
      onStudioSelect={handleStudioSelect}
      onNavigateToSet={handleNavigateToSet}
      onSprachNavigate={handleSprachNavigate}
      onAskChat={handleAskChat}
      onPillClick={handlePillClick}
      refreshProgress={refreshProgress}
      openMindmapInViewer={openMindmapInViewer}
      consumeMindmapViewerOpen={consumeMindmapViewerOpen}
      openDataTableInViewer={openDataTableInViewer}
      consumeDataTableViewerOpen={consumeDataTableViewerOpen}
      onMinimize={onMinimize}
      hideHeader={hideHeader}
      chatLang={chatLang}
    />
    </div>
  );

  // Sources panel content (viewer or source list): mobile + desktop shared
  const renderQuellenContent = ({ onMinimize, hideHeader: hh }: { onMinimize: () => void; hideHeader: boolean }) => {
    if (viewerSource) {
      return _isMediaFile(viewerSource.filename) ? (
        <MediaPlayer source={viewerSource} onClose={handleCloseViewer} workspaceUuid={uuid} onMinimize={onMinimize} canManage={isOwner} onSaveNote={addNote} />
      ) : (
        <PdfViewer source={viewerSource} onClose={handleCloseViewer} workspaceUuid={uuid} onAskWithSelection={handleAskWithSelection} onCustomQuestion={handleCustomQuestion} popupActions={popupActions} onAddToGlossary={handleAddToGlossary} onAddToNote={handleAddToNote} onMinimize={onMinimize} />
      );
    }
    return (
      <SourcesPanel
        sources={sources}
        selectedSourceIds={selectedSourceIds}
        onToggleSource={handleToggleSource}
        onOpenViewer={(src) => handleOpenViewer(src)}
        onDeleteSource={handleDeleteSource}
        onRenameSource={handleRenameSource}
        onRetrySource={handleRetrySource}
        onUpload={handleUpload}
        uploadProgress={uploadProgress}
        uploadErrors={uploadErrors}
        onDismissUploadErrors={() => setUploadErrors([])}
        isOwner={isOwner}
        ocrEnabled={moduleDetail?.ocr_enabled ?? true}
        onMinimize={onMinimize}
        workspaceUuid={uuid}
        staffNoteText={moduleDetail?.staff_note_text ?? null}
        staffNoteLinks={moduleDetail?.staff_note_links ?? []}
        onStaffNoteSave={handleStaffNoteSave}
        chapters={chapters}
        onCreateChapter={handleCreateChapter}
        onRenameChapter={handleRenameChapter}
        onDeleteChapter={handleDeleteChapter}
        onMoveChapter={handleMoveChapter}
        onSetSourceChapter={handleSetSourceChapter}
        closedChapters={closedChapters}
        onToggleChapterOpen={toggleChapterOpen}
        {...(hh ? { hideHeader: true } : {})}
      />
    );
  };

  // Without a level the assessment takes over the middle column.
  const renderChatContent = ({ onMinimize, hideHeader: hh }: { onMinimize: () => void; hideHeader: boolean }) => {
    if (diagnosisActive) {
      return (
        <LanguageDiagnosisPanel
          userId={me?.id ?? null}
          hideHeader={hh}
          onComplete={() => {
            // Re-fetch /me so language_level reflects the persisted value
            fetch("/api/me", { credentials: "include" })
              .then((r) => (r.ok ? r.json() : null))
              .then((data) => { if (data) setMe({ id: data.id, language_level: data.language_level }); })
              .catch(() => { /* ignore */ });
          }}
          onAbort={() => setLanguageTrainingActive(false)}
        />
      );
    }
    return (
      <ChatPanel
        messages={messages}
        activeSourceIds={activeSourceIds}
        sources={sources}
        isAdmin={isAdmin}
        popupActions={popupActions}
        loading={chatLoading}
        onSend={(v) => sendChatMessage(v)}
        onStop={stopChat}
        onSendPrompt={(text) => sendChatMessage(text)}
        onPillClick={handlePillClick}
        moduleReady={moduleDetail?.status === "ready"}
        onClear={() => {
          const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : "";
          fetch(`/api/ai-assistant/workspaces/${uuid}/messages${eidParam}`, { method: "DELETE", credentials: "include" });
          setMessages([]);
        }}
        externalTextareaRef={chatTextareaRef}
        onSaveNote={addNote}
        onRetry={retryLast}
        onMinimize={onMinimize}
        registerSetInput={registerChatSetInput}
        {...(hh ? { hideHeader: true } : {})}
      />
    );
  };

  // The course is inactive, the page says so and offers the way back.
  if (locked) {
    return (
      <ProtectedRoute>
        <div className="aia-scale flex flex-col overflow-hidden" style={{ height: "100vh" }}>
          <Header showLogout />
          <div className="flex-1 flex items-center justify-center px-6">
            <div
              className="max-w-md w-full rounded-xl p-8 text-center"
              style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
            >
              <Lock size={32} weight="fill" className="mx-auto mb-4" style={{ color: "var(--muted)" }} />
              <h1 className="text-lg font-semibold mb-2" style={{ color: "var(--foreground)" }}>
                {tClosed("title")}
              </h1>
              <p className="text-sm mb-6" style={{ color: "var(--muted)" }}>
                {tClosed("text")}
              </p>
              <Link href="/" className="btn-primary inline-block px-6 py-2.5 rounded-lg text-sm font-medium">
                {tClosed("back")}
              </Link>
            </div>
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  if (!initialized) {
    return (
      <ProtectedRoute>
        <div className="aia-scale flex flex-col overflow-hidden" style={{ height: "100vh" }}>
          <div className="flex-1 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      {/* Der KI-Assistent bleibt auf der alten, kompakteren Schriftskala,
          siehe .aia-scale in globals.css. display:contents reicht die
          Variablen nach unten durch, ohne eine eigene Box zu bauen, und
          erwischt so auch das Modal ausserhalb des 100vh-Rahmens. */}
      <OwnerPreviewProvider value={ownerPreview}>
      <div className="aia-scale" style={{ display: "contents" }}>
      <div className="flex flex-col overflow-hidden mobile-flow" style={{ height: "100vh" }}>
        <WorkspaceTopbar
          isMobile={isMobile}
          title={moduleDetail?.title ?? ""}
          canPreview={canPreview}
          previewOn={previewOn}
          previewsOwnerSide={previewsOwnerSide}
          onTogglePreview={() => setPreviewOverride(!previewOn)}
          onStartTour={() => {
            // Erst das Fenster zu, sonst verdeckt es genau die Stellen, auf die gezeigt wird.
            setShowSettings(false);
            setTimeout(starteRundgang, 250);
          }}
          showSettings={showSettings}
          onToggleSettings={() => setShowSettings((v) => !v)}
          onCloseSettings={() => setShowSettings(false)}
          studioEnabled={studioEnabled}
          onToggleStudio={() => setStudioEnabled((v) => !v)}
          language_trainingActive={language_trainingActive}
          languageTrainingAvailable={languageTrainingAvailable}
          onToggleLanguageTraining={handleToggleLanguageTraining}
          languageTrainingOptIn={languageTrainingOptIn}
          onToggleLanguageTrainingOptIn={() => setLanguageTrainingOptIn((v) => !v)}
          isOwner={isOwner}
          transcriptTargetLang={transcriptTargetLang}
          onChangeTranscriptTargetLang={handleChangeTranscriptTargetLang}
          popupTranslateLang={popupTranslateLang}
          onChangePopupTranslateLang={setPopupTranslateLang}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          languageLevel={me?.language_level ?? null}
          onResetLanguageLevel={async () => {
            await fetch("/api/ai-assistant/language-diagnosis/me", {
              method: "DELETE",
              credentials: "include",
            });
            setMe((prev) => (prev ? { ...prev, language_level: null } : prev));
          }}
        />


        <WorkspacePanelsLayout
          isMobile={isMobile}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          panels={effectivePanels}
          togglePanel={togglePanel}
          panelContainerRef={panelContainerRef}
          p1Ref={p1Ref} p2Ref={p2Ref} p3Ref={p3Ref}
          p1Style={p1Style} p2Style={p2Style} p3Style={p3Style}
          studioEnabled={studioEnabled}
          canDrag={canDrag}
          startDrag={startDrag}
          renderQuellen={renderQuellenContent}
          renderChat={renderChatContent}
          renderStudio={({ onMinimize, hideHeader }) => renderStudioPanel(onMinimize, hideHeader)}
          diagnosisActive={diagnosisActive}
        />
      </div>
      {/* Create Set Modal */}
      {showCreateModal && (
        <CreateSetModal
          tool={createSetTool}
          glossaryCount={glossaryCount || glossary.length}
          selectedSources={selectedSourcesForSet}
          workspaceUuid={uuid}
          canManage={isOwner}
          currentUserId={me?.id ?? null}
          onClose={() => setShowCreateModal(false)}
          onCreate={async (mode, count, grammarTopicId, grammarKinds, flashcardSetId) => {
            setShowCreateModal(false);
            if (createSetTool === "quiz" || createSetTool === "karteikarten") {
              // Studio tools stay in Studio
              setStudioView(createSetTool as StudioView);
            } else {
              const prefix = createSetTool === "flashcards" ? "lk"
                : createSetTool === "wortschatz" ? "wo" : "gr";
              const setsView = `${prefix}-sets` as LanguageTrainingView;
              setSprachView(setsView);
            }
            await createExerciseSet(
              createSetTool, mode, count,
              // The card path needs the sources too, the text comes from them.
              mode === "glossary" ? undefined : setSourceUuids,
              grammarTopicId,
              grammarKinds,
              flashcardSetId,
            );
            const poll = setInterval(() => loadExerciseSets(createSetTool), 3000);
            setTimeout(() => clearInterval(poll), 120000);
          }}
        />
      )}
      </div>
      </OwnerPreviewProvider>
    </ProtectedRoute>
  );
}
