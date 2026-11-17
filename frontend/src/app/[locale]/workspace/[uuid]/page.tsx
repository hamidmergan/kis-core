"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useParams, useSearchParams } from "next/navigation";
import Spinner from "@/components/ui/Spinner";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { isFullAdmin } from "@/lib/permissions";

import type {
  ViewerState,
  StudioView,
  LanguageTrainingView,
  StaffNoteLink,
} from "./_types";
import { _isMediaFile } from "./_utils";
import { NOTE_BODY_MAX } from "./_constants";
import { readYoutubeConsent, writeYoutubeConsent } from "@/lib/youtubeConsent";
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
import { useWorkspaceDetail } from "./_hooks/useWorkspaceDetail";
import { usePersistWorkspaceSettings, useWorkspaceSettings } from "./_hooks/useWorkspaceSettings";
import { useLanguageTrainingVisible } from "./_hooks/useLanguageTrainingVisible";
import { useScheduleDeepLink, useStudioTabs } from "./_hooks/useStudioTabs";

// Lightweight components needed on initial render
import { SourcesPanel } from "./_components/sources/SourcesPanel";
import { ChatPanel } from "./_components/chat/ChatPanel";
import { CreateSetModal } from "./_components/language_training/CreateSetModal";
import { GlossaryView } from "./_components/language_training/GlossaryView";
import { WorkspaceTopbar } from "./_components/layout/WorkspaceTopbar";
import { OwnerPreviewProvider } from "./_components/layout/OwnerOnly";
import { resolvePreview } from "./_preview";
import { useWorkspaceTour } from "./_tour/useWorkspaceTour";
import { LoadingScreen, LockedScreen } from "./_screens";
import { WorkspacePanelsLayout } from "./_components/layout/WorkspacePanelsLayout";
import { StudioPanelContent } from "./_components/studio/StudioPanelContent";
import { LanguageTrainingContent } from "./_components/language_training/LanguageTrainingContent";

// Heavy / conditionally-rendered components: loaded on demand to keep initial bundle small
const dynamicLoader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const PdfViewer = dynamic(() => import("./_components/viewer/PdfViewer").then((m) => ({ default: m.PdfViewer })), { loading: dynamicLoader, ssr: false });
const MediaPlayer = dynamic(() => import("./_components/viewer/MediaPlayer").then((m) => ({ default: m.MediaPlayer })), { loading: dynamicLoader, ssr: false });
const NotesStudio = dynamic(() => import("./_components/studio/NotesStudio").then((m) => ({ default: m.NotesStudio })), { loading: dynamicLoader, ssr: false });

// One array for every render without links, a fresh one would re-render the topbar's note editor.
const NO_STAFF_NOTE_LINKS: StaffNoteLink[] = [];

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function KiTutorWorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const uuid = params.uuid as string;
  const enrollmentId = searchParams.get("eid") ? Number(searchParams.get("eid")) : null;
  const initialTab = searchParams.get("tab");

  const {
    moduleDetail, setWorkspaceDetail,
    saveStaffNote: handleStaffNoteSave,
    toggleActive: handleToggleActive,
  } = useWorkspaceDetail(uuid);

  const {
    sources, setSources,
    selectedSourceIds, setSelectedSourceIds,
    uploadProgress,
    uploadErrors, setUploadErrors,
    toggleSource: handleToggleSource,
    deleteSource: handleDeleteSource,
    renameSource: handleRenameSource,
    retrySource: handleRetrySource,
    summarizeSource: handleSummarizeSource,
    uploadFiles: handleUpload,
    addLink: handleAddLink,
    addYoutube: handleAddYoutube,
    addPage: handleAddPage,
    addText: handleAddText,
    editText: handleEditText,
  } = useSources({ uuid, onModuleUpdate: setWorkspaceDetail });

  // Chapters only structure the list, the selection stays the file's checkbox.
  const {
    chapters, setChapters,
    closedChapters, toggleChapterOpen, openChapter,
    createChapter: handleCreateChapter,
    renameChapter: handleRenameChapter,
    deleteChapter: handleDeleteChapter,
    moveChapter: handleMoveChapter,
    setSourceChapter: handleSetSourceChapter,
    moveSource: handleMoveSource,
  } = useChapters({ uuid, setSources });

  // The course room is the one truth, the structure comes along every time.
  useEffect(() => {
    if (moduleDetail?.chapters) setChapters(moduleDetail.chapters);
  }, [moduleDetail?.chapters, setChapters]);

  const [viewerSource, setViewerSource] = useState<ViewerState | null>(null);
  // The recording whose transcript was opened for correcting, from the source menu.
  const [transcriptEditFor, setTranscriptEditFor] = useState<string | null>(null);
  // One click, ever, per browser: the choice is remembered in localStorage.
  const [youtubeConsent, setYoutubeConsent] = useState(readYoutubeConsent);

  const {
    panels, setPanels,
    p1Style, p2Style, p3Style, canDrag,
    activeTab, setActiveTab,
    isMobile,
    panelContainerRef, p1Ref, p2Ref, p3Ref,
    togglePanel, showPanel, focusPanel, startDrag,
  } = usePanelLayout({ uuid, viewerSource });

  const settings = useWorkspaceSettings();
  const { studioEnabled, setStudioEnabled, popupTranslateLang, setPopupTranslateLang } = settings;

  const {
    messages,
    chatLoading, popupActions,
    chatTextareaRef, chatSetInputRef,
    registerChatSetInput,
    loadMessages, clearMessages, sendChatMessage, stopChat, retryLast,
  } = useChat({ uuid, enrollmentId, selectedSourceIds, popupTranslateLang });

  const [showSettings, setShowSettings] = useState(false);
  // null means nobody pressed the switch yet, then the default per course counts.
  const [previewOverride, setPreviewOverride] = useState<boolean | null>(null);
  const language_trainingVisible = useLanguageTrainingVisible();

  const [studioView, setStudioView] = useState<StudioView>("overview");
  const mm = useMindmap({ uuid, selectedSourceIds });
  const dt = useDataTable({ uuid, selectedSourceIds });
  const { notes, setNotes, loadNotes, pendingTitleIds, addNote, deleteNote, updateNoteTitle } = useNotes({ uuid });
  const { studioTabRequest, clearStudioTabRequest, openStudioTab } = useStudioTabs(showPanel);

  const ex = useExercises({ uuid });
  const {
    exerciseSets, activeSet, setActiveSet,
    createSetTool, setCreateSetTool, showCreateModal, setShowCreateModal,
    loadExerciseSets, loadExerciseSet, createExerciseSet, deleteExerciseSet, renameExerciseSet,
    retryExerciseSet, downloadExerciseSet, submitSingleAnswer, watchExerciseSets,
  } = ex;

  // The start page invitation lands directly in the tour; handled here too, since without enrolment the first fetch below rejects the person before the tour starts.
  const tourAngefordert = searchParams.get("tour") === "1";

  const { auth, initialized, locked } = useWorkspaceInit({
    uuid,
    tourAngefordert,
    setSources,
    setSelectedSourceIds,
    setWorkspaceDetail,
    setNotes,
    loadMessages,
    onSettingsLoaded: settings.applyLoaded,
  });
  usePersistWorkspaceSettings(uuid, initialized, settings);

  const { statsVersion, loadStreak, bumpStats } = useStats({ uuid, initialized });

  // Reset mobile tab if studio is disabled
  useEffect(() => {
    if (!studioEnabled && activeTab === "studio") setActiveTab("chat");
  }, [studioEnabled, activeTab]);

  useScheduleDeepLink({ ready: initialized && studioEnabled, initialTab, openStudioTab });

  const {
    openViewer: handleOpenViewer,
    closeViewer: handleCloseViewer,
    openGlossarySource: handleOpenGlossarySource,
    askWithSelection: handleAskWithSelection,
    askChat: handleAskChat,
    customQuestion: handleCustomQuestion,
    pillClick: handlePillClick,
  } = useViewerActions({
    workspaceUuid: uuid,
    sources, selectedSourceIds,
    setViewerSource, setPanels, panels,
    isMobile, activeTab, setActiveTab,
    chatSetInputRef, chatTextareaRef, sendChatMessage,
  });

  // Wrapper: glossary extraction with UI navigation to the glossary tab
  async function handleAddToGlossary(text: string, sourceUuid: string, page: number) {
    setSprachView("overview");
    setStudioView("overview");
    openStudioTab("glossary");
    await extractGlossary(text, sourceUuid, page);
  }

  // Saves the PDF selection as a note with a citation chip back to the spot.
  async function handleAddToNote(text: string, sourceUuid: string, page: number) {
    const citation = ` [Q1:${sourceUuid}, S. ${page}]`;
    const bodyBudget = NOTE_BODY_MAX - citation.length;
    const truncated = text.length > bodyBudget ? text.slice(0, bodyBudget - 1) + "…" : text;
    setSprachView("overview");
    setStudioView("overview");
    openStudioTab("notes");
    await addNote(
      truncated + citation,
      [sourceUuid],
      { popupSelection: { uuid: sourceUuid, page, text: truncated } },
    );
  }

  const {
    langTrainingView, setSprachView,
    glossary, glossaryCount, glossaryExtracting, glossaryFeedback,
    deleteGlossaryEntry, deleteAllGlossaryEntries,
    loadGlossary, loadGlossaryCount,
    extractGlossary, dismissFeedback,
  } = useLanguageTraining({ uuid });

  // Studio navigation (see useStudioNavigation)
  const {
    handleStudioSelect, handleNavigateToSet, handleSprachNavigate, refreshProgress,
    openMindmapInViewer, consumeMindmapViewerOpen,
    openDataTableInViewer, consumeDataTableViewerOpen,
  } = useStudioNavigation({
    studioView, setStudioView, setSprachView,
    loadExerciseSets, loadExerciseSet,
    selectMindmap: mm.select, selectDataTable: dt.select,
    loadStreak, bumpStats,
  });

  // Without the right to create modules there is no teacher preview and no tour steps pointing at its buttons.
  const darfModuleAnlegen = auth?.permissions?.allow_workspace_create ?? false;
  const { starteRundgang } = useWorkspaceTour({
    uuid, initialized, tourAngefordert,
    istDemoModul: moduleDetail?.is_demo_workspace ?? false,
    darfModuleAnlegen,
    sources, openChapter, setSelectedSourceIds,
    openViewer: handleOpenViewer, closeViewer: handleCloseViewer,
    setStudioView, openStudioTab, showPanel,
    loadGlossary, loadGlossaryCount, loadNotes, loadMessages, loadStreak, bumpStats,
  });

  // All chosen sources, the backend spreads the budget over every one of them.
  const selectedSourcesForSet = selectedSourceIds
    .map((id) => sources.find((s) => s.uuid === id))
    .filter((s): s is NonNullable<typeof s> => Boolean(s))
    .map((s) => ({ uuid: s.uuid, filename: s.filename }));

  const isAdmin = auth?.is_admin ?? false;
  // The adaptive level line is a debug hint, is_admin is already true for any settings right.
  const isFullAdminUser = isFullAdmin(auth?.permissions);

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
    />
  );

  const glossaryContent = (
    <GlossaryView
      entries={glossary}
      extracting={glossaryExtracting}
      onOpenSource={handleOpenGlossarySource}
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
  // Studio panel content (mobile + desktop identical, only the panel context differs)
  const renderStudioPanel = ({ onMinimize, hideHeader }: { onMinimize: () => void; hideHeader: boolean }) => (
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
    />
    </div>
  );

  // Sources panel content (viewer or source list): mobile + desktop shared
  const renderQuellenContent = ({ onMinimize, hideHeader: hh }: { onMinimize: () => void; hideHeader: boolean }) => {
    if (viewerSource) {
      return _isMediaFile(viewerSource.filename) ? (
        <MediaPlayer source={viewerSource} onClose={handleCloseViewer} workspaceUuid={uuid} onMinimize={onMinimize} canManage={isOwner} onSaveNote={addNote} youtubeConsent={youtubeConsent} onYoutubeConsent={() => { writeYoutubeConsent(); setYoutubeConsent(true); }} editTranscript={transcriptEditFor === viewerSource.uuid} onEditTranscriptEnd={() => setTranscriptEditFor(null)} />
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
        onEditTranscript={isOwner ? (src) => { setTranscriptEditFor(src.uuid); handleOpenViewer(src); } : undefined}
        onDeleteSource={handleDeleteSource}
        onRenameSource={handleRenameSource}
        onRetrySource={handleRetrySource}
        onSummarizeSource={handleSummarizeSource}
        onUpload={handleUpload}
        onAddLink={handleAddLink}
        onAddYoutube={handleAddYoutube}
        onAddPage={handleAddPage}
        onAddText={handleAddText}
        onEditText={handleEditText}
        textMaxChars={moduleDetail?.text_source_max_chars}
        uploadProgress={uploadProgress}
        uploadErrors={uploadErrors}
        onDismissUploadErrors={() => setUploadErrors([])}
        isOwner={isOwner}
        ocrEnabled={moduleDetail?.ocr_enabled ?? true}
        onMinimize={onMinimize}
        workspaceUuid={uuid}
        chapters={chapters}
        onCreateChapter={handleCreateChapter}
        onRenameChapter={handleRenameChapter}
        onDeleteChapter={handleDeleteChapter}
        onMoveChapter={handleMoveChapter}
        onSetSourceChapter={handleSetSourceChapter}
        onMoveSource={handleMoveSource}
        closedChapters={closedChapters}
        onToggleChapterOpen={toggleChapterOpen}
        {...(hh ? { hideHeader: true } : {})}
      />
    );
  };

  const renderChatContent = ({ onMinimize, hideHeader: hh }: { onMinimize: () => void; hideHeader: boolean }) => {
    return (
      <ChatPanel
        messages={messages}
        activeSourceIds={selectedSourceIds}
        sources={sources}
        isAdmin={isFullAdminUser}
        popupActions={popupActions}
        loading={chatLoading}
        onSend={(v) => sendChatMessage(v)}
        onStop={stopChat}
        onPillClick={handlePillClick}
        onClear={clearMessages}
        externalTextareaRef={chatTextareaRef}
        onSaveNote={addNote}
        onRetry={retryLast}
        onMinimize={onMinimize}
        registerSetInput={registerChatSetInput}
        {...(hh ? { hideHeader: true } : {})}
      />
    );
  };

  if (locked) return <LockedScreen />;
  if (!initialized) return <LoadingScreen />;

  return (
    <ProtectedRoute>
      {/* The AI assistant keeps the old compact font scale (.aia-scale in globals.css); display:contents passes the variables down without a box and reaches the modal outside the 100vh frame. */}
      <OwnerPreviewProvider value={ownerPreview}>
      <div className="aia-scale" style={{ display: "contents" }}>
      <div className="flex flex-col overflow-hidden viewport-shell">
        <WorkspaceTopbar
          isMobile={isMobile}
          title={moduleDetail?.title ?? ""}
          canPreview={canPreview}
          previewOn={previewOn}
          previewsOwnerSide={previewsOwnerSide}
          onTogglePreview={() => setPreviewOverride(!previewOn)}
          isOwner={isOwner}
          staffNoteText={moduleDetail?.staff_note_text ?? null}
          staffNoteLinks={moduleDetail?.staff_note_links ?? NO_STAFF_NOTE_LINKS}
          onStaffNoteSave={handleStaffNoteSave}
          canManage={isOwner}
          workspaceUuid={uuid}
          isActive={moduleDetail?.is_active ?? true}
          onToggleActive={handleToggleActive}
          onStartTour={() => {
            // Close the modal first, otherwise it covers the very spots being pointed at.
            setShowSettings(false);
            setTimeout(starteRundgang, 250);
          }}
          isTourModule={moduleDetail?.is_tour_module ?? false}
          showSettings={showSettings}
          onToggleSettings={() => setShowSettings((v) => !v)}
          onCloseSettings={() => setShowSettings(false)}
          studioEnabled={studioEnabled}
          onToggleStudio={() => setStudioEnabled((v) => !v)}
          popupTranslateLang={popupTranslateLang}
          onChangePopupTranslateLang={setPopupTranslateLang}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />


        <WorkspacePanelsLayout
          isMobile={isMobile}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          panels={panels}
          togglePanel={togglePanel}
          focusPanel={focusPanel}
          panelContainerRef={panelContainerRef}
          p1Ref={p1Ref} p2Ref={p2Ref} p3Ref={p3Ref}
          p1Style={p1Style} p2Style={p2Style} p3Style={p3Style}
          studioEnabled={studioEnabled}
          canDrag={canDrag}
          startDrag={startDrag}
          renderQuellen={renderQuellenContent}
          renderChat={renderChatContent}
          renderStudio={renderStudioPanel}
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
          currentUserId={auth?.user_id ?? null}
          onClose={() => setShowCreateModal(false)}
          onCreate={async (mode, count, grammarTopicId, grammarKinds, flashcardSetId, instruction) => {
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
              mode === "glossary" ? undefined : selectedSourceIds,
              grammarTopicId,
              grammarKinds,
              flashcardSetId,
              instruction,
            );
            watchExerciseSets(createSetTool);
          }}
        />
      )}
      </div>
      </OwnerPreviewProvider>
    </ProtectedRoute>
  );
}
