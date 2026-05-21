"use client";

import React, { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useParams, useSearchParams } from "next/navigation";
import Spinner from "@/components/ui/Spinner";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";

import type {
  WorkspaceDetail,
  ViewerState,
  StudioView,
  LanguageTrainingView,
  TranscriptTranslationMode,
  TranscriptDefaultLang,
  StaffNoteLink,
} from "./_types";
import { _isMediaFile } from "./_utils";
import { NOTE_BODY_MAX } from "./_constants";
import { usePanelLayout } from "./_hooks/usePanelLayout";
import { useSources } from "./_hooks/useSources";
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
  const uuid = params.uuid as string;
  const enrollmentId = searchParams.get("eid") ? Number(searchParams.get("eid")) : null;
  const initialTab = searchParams.get("tab");

  const [moduleDetail, setWorkspaceDetail] = useState<WorkspaceDetail | null>(null);
  // auth + initialized come from useWorkspaceInit (after all source/chat hooks)

  // Layout state (panels, widths, mobile detection, drag): see usePanelLayout
  // Defined after viewerSource because the hook needs viewerSource as input.

  const {
    sources, setSources,
    selectedSourceIds, setSelectedSourceIds,
    prevSelectedSourceIds, setPrevSelectedSourceIds,
    uploadProgress,
    uploadErrors, setUploadErrors,
    toggleSource: handleToggleSource,
    deleteSource: handleDeleteSource,
    retrySource: handleRetrySource,
    uploadFiles: handleUpload,
  } = useSources({ uuid, onModuleUpdate: (mod) => setWorkspaceDetail(mod) });

  const [viewerSource, setViewerSource] = useState<ViewerState | null>(null);

  const {
    panels, setPanels,
    p1Width, p2Width, p3Width,
    activeTab, setActiveTab,
    isMobile,
    hideHeader, setHideHeader,
    panelContainerRef, p1Ref, p2Ref, p3Ref,
    togglePanel, startDrag,
  } = usePanelLayout({ uuid, viewerSource });

  const [chatLang, setChatLang] = useState<"de" | "en">("de");

  const chat = useChat({ uuid, enrollmentId, selectedSourceIds, viewerSource, chatLang });
  const {
    messages, setMessages,
    chatLoading, popupActions,
    chatTextareaRef,
    registerChatSetInput,
    loadMessages, sendChatMessage, stopChat,
    chatSetInputRef,
  } = chat;

  const [showSettings, setShowSettings] = useState(false);


  const [studioEnabled, setStudioEnabled] = useState(true);
  const [language_trainingActive, setLanguageTrainingActive] = useState(false);

  // Language level diagnosis: triggered when Fachsprachentrainer toggles on
  // for a user without a stored language_level. Fetched once at mount.
  const [me, setMe] = useState<{ id: number; language_level: string | null } | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (!cancelled && data) setMe({ id: data.id, language_level: data.language_level }); })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, []);
  const diagnosisActive = language_trainingActive && me !== null && me.language_level === null;
  // While diagnosis runs, force sources & studio minimized so the user focuses
  // on the diagnosis panel. The MiniStrip buttons are disabled separately, so
  // the user can't re-expand them until the diagnosis is done or aborted.
  useEffect(() => {
    if (!diagnosisActive) return;
    setPanels((prev) =>
      prev.quellen || prev.studio ? { ...prev, quellen: false, studio: false } : prev,
    );
  }, [diagnosisActive, setPanels]);

  const [translationMode, setTranslationMode] = useState<TranscriptTranslationMode>("manual");
  useEffect(() => {
    if (moduleDetail?.transcript_translation_mode) {
      setTranslationMode(moduleDetail.transcript_translation_mode);
    }
  }, [moduleDetail?.transcript_translation_mode]);
  const handleChangeTranslationMode = (mode: TranscriptTranslationMode) => {
    setTranslationMode(mode);
    fetch(`/api/ai-assistant/workspaces/${uuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript_translation_mode: mode }),
    }).catch(() => { /* ignore */ });
  };
  const [transcriptDefaultLang, setTranscriptDefaultLang] = useState<TranscriptDefaultLang>("both");
  useEffect(() => {
    if (moduleDetail?.transcript_default_lang) {
      setTranscriptDefaultLang(moduleDetail.transcript_default_lang);
    }
  }, [moduleDetail?.transcript_default_lang]);
  const handleChangeTranscriptDefaultLang = (lang: TranscriptDefaultLang) => {
    setTranscriptDefaultLang(lang);
    fetch(`/api/ai-assistant/workspaces/${uuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript_default_lang: lang }),
    }).catch(() => { /* ignore */ });
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
  const { mindmapData, mindmapLoading, mindmapList } = mm;
  const generateMindmap = mm.generate;
  const selectMindmap = mm.select;
  const deleteMindmap = mm.remove;

  const dt = useDataTable({ uuid, selectedSourceIds });
  const { data_table, data_tableSources, data_tableLoading, data_tableList } = dt;
  const generateDataTable = dt.generate;
  const selectDataTable = dt.select;
  const deleteDataTable = dt.remove;
  const { notes, setNotes, pendingTitleIds, addNote, deleteNote, updateNoteTitle } = useNotes({ uuid });

  // ─── Language training state ─────────────────────────────────────────────
  const [studioTabRequest, setStudioTabRequest] = useState<{ tab: "tools" | "glossary" | "notes" | "statistik" | "schedule"; nonce: number } | null>(null);
  // Language training state: see useLanguageTraining (init after selectedSourceIds)

  // ─── Exercise sets state ─────────────────────────────────────────────────
  const ex = useExercises({ uuid });
  const {
    exerciseSets, activeSet, setActiveSet,
    createSetTool, setCreateSetTool, showCreateModal, setShowCreateModal,
    loadExerciseSets, loadExerciseSet, createExerciseSet, deleteExerciseSet,
    downloadExerciseSet, submitSingleAnswer,
  } = ex;
  // streakInfo, pageStats, statsVersion aus useStats (init nach initialized-Flag)
  // glossaryCount aus useLanguageTraining

  // ─── Init (see useWorkspaceInit) ─────────────────────────────────────────
  const { auth, initialized } = useWorkspaceInit({
    uuid,
    setSources,
    setSelectedSourceIds,
    setWorkspaceDetail,
    setNotes,
    loadMessages,
    onSettingsLoaded: (s) => {
      setChatLang(s.chat_lang);
      setStudioEnabled(s.studio_enabled);
      setLanguageTrainingActive(s.language_training_active);
    },
  });

  const { streakInfo, pageStats, statsVersion, loadStreak, bumpStats } = useStats({ uuid, initialized });

  // Reset mobile tab if studio is disabled
  useEffect(() => {
    if (!studioEnabled && activeTab === "studio") setActiveTab("chat");
  }, [studioEnabled, activeTab]);

  // Deep-link: arrive from /schedule with ?tab=schedule → open studio panel
  // and jump straight to the schedule tab. Fire-once via ref so a later
  // viewport-resize doesn't yank the user back here after they navigated away.
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
      body: JSON.stringify({ chat_lang: chatLang, studio_enabled: studioEnabled, language_training_active: language_trainingActive }),
    }).catch(() => { /* ignore */ });
  }, [chatLang, studioEnabled, language_trainingActive, initialized, uuid]);

  // ─── Viewer + chat input actions (see useViewerActions) ─────────────────
  const {
    openViewer: handleOpenViewer,
    closeViewer: handleCloseViewer,
    askWithSelection: handleAskWithSelection,
    askChat: handleAskChat,
    customQuestion: handleCustomQuestion,
    pillClick: handlePillClick,
  } = useViewerActions({
    sources, selectedSourceIds, setSelectedSourceIds,
    prevSelectedSourceIds, setPrevSelectedSourceIds,
    setViewerSource, setPanels, panels,
    isMobile, activeTab, setActiveTab,
    chatSetInputRef, chatTextareaRef, sendChatMessage,
  });

  // Wrapper: glossary extraction with UI navigation to the glossary tab
  async function handleAddToGlossary(text: string, sourceUuid: string, page: number) {
    setSprachView("overview");
    setStudioTabRequest({ tab: "glossary", nonce: Date.now() });
    if (isMobile) setActiveTab("studio");
    else setPanels((prev) => ({ ...prev, studio: true }));
    await extractGlossary(text, sourceUuid, page);
  }

  // Wrapper: save PDF selection as a new note with source chip
  // Appends a citation marker so wrapCitations renders an inline, clickable source chip
  // that jumps back to the original page and highlights the selected text.
  async function handleAddToNote(text: string, sourceUuid: string, page: number) {
    const citation = ` [Q1:${sourceUuid}, S. ${page}]`;
    const bodyBudget = NOTE_BODY_MAX - citation.length;
    const truncated = text.length > bodyBudget ? text.slice(0, bodyBudget - 1) + "…" : text;
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
  const langTrainingActiveIds = selectedSourceIds.slice(0, 3);
  const spr = useLanguageTraining({
    uuid,
    langTrainingActiveIds,
    onAfterCloze: () => loadExerciseSets("lueckentext"),
    onAfterVocabTest: () => loadExerciseSets("vokabeltest"),
  });
  const {
    langTrainingView, setSprachView,
    glossary, glossaryLoading, glossaryCount, glossaryExtracting, glossaryFeedback,
    clozeExercises, clozeLoading,
    vocabQuestions, vocabLoading,
    deleteGlossaryEntry, deleteAllGlossaryEntries,
    generateGlossary, generateCloze, generateVocabTest,
    loadGlossary, loadGlossaryCount,
    extractGlossary, dismissFeedback,
  } = spr;

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

  // Build the language_training content tree
  // Helper: selected source for create-set modal
  const selectedSourceForSet = (() => {
    if (selectedSourceIds.length === 0) return null;
    const src = sources.find((s) => s.uuid === selectedSourceIds[0]);
    return src ? { uuid: src.uuid, filename: src.filename } : null;
  })();

  const isAdmin = auth?.is_admin ?? false;

  const language_trainingContent = (
    <LanguageTrainingContent
      langTrainingView={langTrainingView}
      setSprachView={setSprachView}
      glossary={glossary}
      clozeExercises={clozeExercises}
      clozeLoading={clozeLoading}
      vocabQuestions={vocabQuestions}
      vocabLoading={vocabLoading}
      generateCloze={generateCloze}
      generateVocabTest={generateVocabTest}
      exerciseSets={exerciseSets}
      activeSet={activeSet}
      setActiveSet={setActiveSet}
      loadExerciseSet={loadExerciseSet}
      loadExerciseSets={loadExerciseSets}
      deleteExerciseSet={deleteExerciseSet}
      downloadExerciseSet={downloadExerciseSet}
      setCreateSetTool={setCreateSetTool}
      setShowCreateModal={setShowCreateModal}
      submitSingleAnswer={submitSingleAnswer}
      selectedSourceIds={selectedSourceIds}
      pageStats={pageStats}
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
      loading={glossaryLoading}
      extracting={glossaryExtracting}
      onGenerate={generateGlossary}
      sourceCount={selectedSourceIds.length}
      onOpenSource={(filename, page, highlightText, startTime) => {
        const src = (filename && sources.find((s) => s.filename === filename))
          || sources.find((s) => selectedSourceIds.includes(s.uuid));
        if (!src) return;
        if (_isMediaFile(src.filename) && startTime != null) {
          setPrevSelectedSourceIds(selectedSourceIds);
          setSelectedSourceIds([src.uuid]);
          setViewerSource({ uuid: src.uuid, filename: src.filename, page: 0, startTime, nonce: Date.now() });
          setPanels((prev) => ({ ...prev, quellen: true }));
        } else {
          handleOpenViewer(src, page, highlightText, true);
        }
      }}
      onDelete={deleteGlossaryEntry}
      onDeleteAll={deleteAllGlossaryEntries}
      stats={pageStats}
      showTranslation={language_trainingActive}
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

  const isLecturer = !!auth?.permissions?.allow_workspace_create;
  const activeSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;

  const p1Style: React.CSSProperties = panels.quellen
    ? { flex: `1 1 ${p1Width}px`, minWidth: 200, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p2Style: React.CSSProperties = panels.chat
    ? { flex: `1 1 ${p2Width}px`, minWidth: 50, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p3Style: React.CSSProperties = panels.studio
    ? { flex: `1 1 ${p3Width}px`, minWidth: 200, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const openCount = [panels.quellen, panels.chat, panels.studio].filter(Boolean).length;
  const canDrag = openCount >= 2;

  // Studio panel content (mobile + desktop identical, only the panel context differs)
  const renderStudioPanel = (onMinimize: () => void, hideHeader = false) => (
    <StudioPanelContent
      studioView={studioView}
      setStudioView={setStudioView}
      langTrainingView={langTrainingView}
      language_trainingActive={language_trainingActive}
      studioTabRequest={studioTabRequest}
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
      pageStats={pageStats}
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
  );

  // Sources panel content (viewer or source list): mobile + desktop shared
  const renderQuellenContent = ({ onMinimize, hideHeader: hh }: { onMinimize: () => void; hideHeader: boolean }) => {
    if (viewerSource) {
      return _isMediaFile(viewerSource.filename) ? (
        <MediaPlayer source={viewerSource} onClose={handleCloseViewer} workspaceUuid={uuid} onMinimize={onMinimize} canDownload={isLecturer || isAdmin} canManage={isLecturer || isAdmin} onSaveNote={addNote} defaultTranscriptLang={transcriptDefaultLang} />
      ) : (
        <PdfViewer source={viewerSource} onClose={handleCloseViewer} workspaceUuid={uuid} onAskWithSelection={handleAskWithSelection} onCustomQuestion={handleCustomQuestion} popupActions={popupActions} onAddToGlossary={handleAddToGlossary} onAddToNote={handleAddToNote} onMinimize={onMinimize} isOwner={moduleDetail?.is_owner ?? false} />
      );
    }
    return (
      <SourcesPanel
        sources={sources}
        selectedSourceIds={selectedSourceIds}
        onToggleSource={handleToggleSource}
        onOpenViewer={(src) => handleOpenViewer(src)}
        onDeleteSource={handleDeleteSource}
        onRetrySource={handleRetrySource}
        onUpload={handleUpload}
        uploadProgress={uploadProgress}
        uploadErrors={uploadErrors}
        onDismissUploadErrors={() => setUploadErrors([])}
        isLecturer={isLecturer}
        onMinimize={onMinimize}
        workspaceUuid={uuid}
        staffNoteText={moduleDetail?.staff_note_text ?? null}
        staffNoteLinks={moduleDetail?.staff_note_links ?? []}
        onStaffNoteSave={handleStaffNoteSave}
        {...(hh ? { hideHeader: true } : {})}
      />
    );
  };

  // Chat panel content: mobile + desktop shared.
  // While Fachsprachentrainer is on but no language_level is set yet, the
  // diagnosis panel takes over the middle slot until the user completes it.
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
        onMinimize={onMinimize}
        registerSetInput={registerChatSetInput}
        {...(hh ? { hideHeader: true } : {})}
      />
    );
  };

  if (!initialized) {
    return (
      <ProtectedRoute>
        <div className="flex flex-col overflow-hidden" style={{ height: "100vh" }}>
          {!hideHeader && <Header showLogout />}
          <div className="flex-1 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="flex flex-col overflow-hidden mobile-flow" style={{ height: "100vh" }}>
        {!hideHeader && <Header showLogout />}

        <WorkspaceTopbar
          isMobile={isMobile}
          title={moduleDetail?.title ?? ""}
          showSettings={showSettings}
          onToggleSettings={() => setShowSettings((v) => !v)}
          onCloseSettings={() => setShowSettings(false)}
          studioEnabled={studioEnabled}
          onToggleStudio={() => setStudioEnabled((v) => !v)}
          language_trainingActive={language_trainingActive}
          onToggleLanguageTraining={() => setLanguageTrainingActive((v) => !v)}
          isLecturer={isLecturer}
          isOwner={moduleDetail?.is_owner ?? false}
          hideHeader={hideHeader}
          onToggleHideHeader={() => setHideHeader((v) => !v)}
          translationMode={translationMode}
          onChangeTranslationMode={handleChangeTranslationMode}
          transcriptDefaultLang={transcriptDefaultLang}
          onChangeTranscriptDefaultLang={handleChangeTranscriptDefaultLang}
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
          panels={panels}
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
          selectedSource={selectedSourceForSet}
          onClose={() => setShowCreateModal(false)}
          onCreate={async (mode, count) => {
            setShowCreateModal(false);
            if (createSetTool === "quiz" || createSetTool === "karteikarten") {
              // Studio tools stay in Studio
              setStudioView(createSetTool as StudioView);
            } else {
              const setsView = `${createSetTool === "flashcards" ? "lk" : createSetTool === "lueckentext" ? "cl" : "vt"}-sets` as LanguageTrainingView;
              setSprachView(setsView);
            }
            await createExerciseSet(
              createSetTool, mode, count,
              mode === "source" ? selectedSourceIds[0] : undefined,
            );
            const poll = setInterval(() => loadExerciseSets(createSetTool), 3000);
            setTimeout(() => clearInterval(poll), 120000);
          }}
        />
      )}
    </ProtectedRoute>
  );
}
