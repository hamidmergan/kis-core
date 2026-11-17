// Our own entries in the viewer's selection menu: AI actions, copy, glossary, note, question.

import { copyTextFromPromise } from "@/lib/clipboard";
import { EMBEDPDF_ICON_MAP } from "./_icons";
import { selectedCharCount, selectionHasText, withSelectedText, type SelectionState } from "./_pdfSelection";

type Ref<T> = { readonly current: T };

export type PopupAction = { key: string; label: string; icon: string; prompt: string; min_words: number };

export type AskWithSelection = (
  text: string,
  sourceInfo: { uuid: string; filename: string; page: number; selectedText?: string; actionKey?: string },
) => void;

interface CommandDeps {
  t: (key: string) => string;
  actions: PopupAction[] | undefined;
  // Refs so the commands always see the latest values without re-initialising the viewer.
  sourceRef: Ref<{ uuid: string; filename: string }>;
  onAskWithSelectionRef: Ref<AskWithSelection | undefined>;
  onCustomQuestionRef: Ref<((selectedText: string) => void) | undefined>;
  onAddToGlossaryRef: Ref<((text: string, sourceUuid: string, page: number) => void) | undefined>;
  onAddToNoteRef: Ref<((text: string, sourceUuid: string, page: number) => void) | undefined>;
}

/** Registers the commands and rebuilds the selection menu around them. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function registerSelectionCommands(reg: any, deps: CommandDeps): void {
  const { t, actions, sourceRef, onAskWithSelectionRef, onCustomQuestionRef, onAddToGlossaryRef, onAddToNoteRef } = deps;
  const commands = reg.getPlugin?.("commands")?.provides?.();
  const ui = reg.getPlugin?.("ui")?.provides?.();
  if (!commands || !ui) return;

  if (actions?.length && onAskWithSelectionRef.current) {
    for (const action of actions) {
      commands.registerCommand({
        id: `kis.${action.key}`,
        label: action.label,
        description: action.label,
        icon: EMBEDPDF_ICON_MAP[action.icon] ?? "info",
        iconProps: { title: action.label },
        categories: ["kis-actions"],
        visible: (sel: SelectionState) => {
          const totalChars = selectedCharCount(sel);
          if (totalChars === null) return true;
          if (action.min_words <= 1) return totalChars > 0;
          // Average word ~6 chars; use conservative factor of 4
          return totalChars >= action.min_words * 4;
        },
        action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
          withSelectedText(r, documentId, (text, page) => onAskWithSelectionRef.current?.(
            `${action.prompt}\n\n"${text}"`,
            { uuid: sourceRef.current.uuid, filename: sourceRef.current.filename, page: page(), selectedText: text, actionKey: action.key },
          ));
        },
      });
    }
  }

  // Register custom question command – prefills chat input with selected text
  commands.registerCommand({
    id: "kis.custom-question",
    label: t("askQuestion"),
    description: t("askQuestion"),
    icon: "ph-chat-circle",
    iconProps: { title: t("askQuestion") },
    categories: ["kis-actions"],
    visible: selectionHasText,
    action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
      withSelectedText(r, documentId, (text) => onCustomQuestionRef.current?.(text));
    },
  });

  // Our own copy handler so the user gesture is not lost on the phone.
  commands.registerCommand({
    id: "kis.copy-selection",
    label: t("copy"),
    description: t("copySelection"),
    icon: "copy",
    iconProps: { title: t("copy") },
    categories: ["selection", "selection-copy"],
    visible: selectionHasText,
    action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const sel = (r as any).getPlugin?.("selection")?.provides?.();
      if (!sel) return;
      const textTask = sel.getSelectedText?.(documentId);
      const textPromise: Promise<string> = (textTask?.toPromise?.() ?? Promise.resolve([]))
        .then((lines: string[] | string) => (Array.isArray(lines) ? lines : [lines]).join("\n"));
      copyTextFromPromise(textPromise);
      textPromise.finally(() => sel.forDocument?.(documentId)?.clear?.());
    },
  });

  // Register glossary extract command
  commands.registerCommand({
    id: "kis.add-to-glossary",
    label: t("addToGlossary"),
    description: t("addToGlossaryDescription"),
    icon: "ph-book",
    iconProps: { title: t("addToGlossaryTitle") },
    categories: ["kis-actions"],
    visible: selectionHasText,
    action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
      withSelectedText(r, documentId, (text, page) => onAddToGlossaryRef.current?.(text, sourceRef.current.uuid, page()));
    },
  });

  // Register add-to-note command – stores selection as a new note with source chip
  commands.registerCommand({
    id: "kis.add-to-note",
    label: t("addToNote"),
    description: t("addToNoteDescription"),
    icon: "ph-note-pencil",
    iconProps: { title: t("addToNoteTitle") },
    categories: ["kis-actions"],
    visible: selectionHasText,
    action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
      withSelectedText(r, documentId, (text, page) => onAddToNoteRef.current?.(text, sourceRef.current.uuid, page()));
    },
  });

  // Only the AI actions and copying stay in the selection menu.
  const existingSchema = ui.getSchema?.();
  // We replace copy-selection with kis.copy-selection (touch fix, see above)
  const KEEP_DEFAULT_IDS = new Set(["add-highlight"]);
  const existingSelItems: unknown[] = (existingSchema?.selectionMenus?.selection?.items ?? [])
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((it: any) => it?.type !== "command-button" || KEEP_DEFAULT_IDS.has(it?.id))
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((it: any, idx: number, arr: any[]) => {
      // Remove orphaned dividers at start/end or directly next to each other
      if (it?.type !== "divider") return true;
      const next = arr[idx + 1];
      const prev = arr[idx - 1];
      return prev?.type === "command-button" && next?.type === "command-button";
    });
  ui.mergeSchema?.({
    selectionMenus: {
      selection: {
        id: "selection",
        items: [
          { type: "command-button", id: "kis.copy-selection", commandId: "kis.copy-selection", variant: "icon", categories: ["selection", "selection-copy"] },
          ...existingSelItems,
          { type: "divider", id: "kis-custom-divider", categories: ["kis-actions"] },
          { type: "command-button", id: "kis.add-to-glossary", commandId: "kis.add-to-glossary", variant: "icon", categories: ["kis-actions"] },
          { type: "command-button", id: "kis.add-to-note", commandId: "kis.add-to-note", variant: "icon", categories: ["kis-actions"] },
          { type: "command-button", id: "kis.custom-question", commandId: "kis.custom-question", variant: "icon", categories: ["kis-actions"] },
          ...(actions?.length ? actions.map(a => ({
            type: "command-button",
            id: `kis.${a.key}`,
            commandId: `kis.${a.key}`,
            variant: "icon",
            categories: ["kis-actions"],
          })) : []),
        ],
      },
    },
  });
}
