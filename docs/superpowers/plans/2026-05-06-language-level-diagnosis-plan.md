# Language Level Diagnosis Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-time language level diagnostic modal that appears when users enable Fachsprachentraining for the first time, runs 12 B1-level questions, analyzes responses via KI, and stores the determined level globally.

**Architecture:** Backend provides an analysis endpoint that accepts MC answers + free-text answers and returns a language level (A1–C2) + feedback. Frontend Modal isolates the diagnosis flow in a portal, preventing interaction with the normal workspace until complete. DiagnosisChat component mirrors the normal chat UI but manages diagnosis-specific state.

**Tech Stack:** React 19, Next.js (app router), TypeScript, Tailwind, Phosphor Icons, Python/FastAPI, PostgreSQL, Anthropic SDK

---

## File Structure

**New Backend Files:**
- `backend/src/routes/language_level.py` — POST endpoint for analyzing language level

**New Frontend Components:**
- `frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/LanguageLevelDiagnosisModal.tsx` — modal wrapper, portal, state orchestration
- `frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisChat.tsx` — chat UI for diagnosis (question display, message bubbles)
- `frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisResultsScreen.tsx` — results display (level + feedback)

**New Frontend Hooks:**
- `frontend/src/app/[locale]/workspace/[uuid]/_hooks/useDiagnosisChat.ts` — state management for questions/answers/progress

**Modified Backend Files:**
- `backend/src/models/user.py` — add `language_level: str | None` field
- `backend/src/database.py` (or migration file) — add schema alteration

**Modified Frontend Files:**
- `frontend/src/app/[locale]/workspace/[uuid]/page.tsx` — add modal state + render
- `frontend/messages/de.json` — add diagnosis keys
- `frontend/messages/en.json` — add diagnosis keys

---

## Task Sequence

### Task 1: Database & User Model

**Files:**
- Modify: `backend/src/models/user.py`
- Create: `backend/src/migrations/<timestamp>_add_language_level.py` (Alembic format)

- [ ] **Step 1: Add language_level field to User model**

Open `backend/src/models/user.py` and add this field:

```python
class User(Base):
    # ... existing fields ...
    language_level: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # Valid values: 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'
```

- [ ] **Step 2: Create Alembic migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "add language_level to users"
```

Expected: File created at `backend/src/migrations/versions/<timestamp>_add_language_level_to_users.py`

- [ ] **Step 3: Review generated migration**

Open the generated migration file. It should have:
```python
def upgrade() -> None:
    op.add_column('users', sa.Column('language_level', sa.String(length=5), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'language_level')
```

- [ ] **Step 4: Apply migration locally**

```bash
alembic upgrade head
```

Expected: Migration applied, no errors.

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/user.py backend/src/migrations/versions/*_add_language_level_to_users.py
git commit -m "feat(db): add language_level field to users table"
```

---

### Task 2: Backend API Endpoint for Language Level Analysis

**Files:**
- Create: `backend/src/routes/language_level.py`
- Modify: `backend/src/main.py` (add router import)

- [ ] **Step 1: Create the language_level.py route file**

```python
# backend/src/routes/language_level.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import anthropic
import json
from sqlalchemy.orm import Session
from backend.src.models.user import User
from backend.src.database import get_db

router = APIRouter(prefix="/api/workspaces", tags=["language-level"])

class MCAnswer(BaseModel):
    question_id: int
    selected: str
    correct: bool

class FreeTextAnswer(BaseModel):
    question_id: int
    answer: str

class AnalyzeLanguageLevelRequest(BaseModel):
    mc_answers: list[MCAnswer]
    free_text_answers: list[FreeTextAnswer]

class LanguageLevelResponse(BaseModel):
    language_level: str
    feedback: str
    confidence: float

CORRECT_ANSWERS = {
    1: "A",  # wann der Zug kommt
    2: ["A", "C"],  # Perfekt: ist gefahren, haben telefoniert
    3: "A",  # auf den Bus warten
    4: "B",  # weil ich krank bin
    5: "B",  # unpünktlich
    6: ["B", "C"],  # schnell, groß
    7: "A",  # nett
    8: "B",  # Später
    9: "A",  # Die Rechnung bitte
}

@router.post("/{uuid}/language-level/analyze")
async def analyze_language_level(
    uuid: str,
    request: AnalyzeLanguageLevelRequest,
    db: Session = Depends(get_db),
) -> LanguageLevelResponse:
    """Analyze language level from MC and free-text responses."""
    
    # Calculate MC accuracy
    correct_count = 0
    for answer in request.mc_answers:
        expected = CORRECT_ANSWERS.get(answer.question_id, [])
        if isinstance(expected, list):
            if answer.selected in expected:
                correct_count += 1
        else:
            if answer.selected == expected:
                correct_count += 1
    
    mc_accuracy = correct_count / len(request.mc_answers) if request.mc_answers else 0
    
    # Prepare free-text responses for KI
    free_text_str = "\n".join([
        f"Q{a.question_id}: {a.answer}"
        for a in request.free_text_answers
    ])
    
    # Call Anthropic API with analysis prompt
    client = anthropic.Anthropic()
    
    prompt = f"""You are a German language proficiency assessor. Analyze these responses and determine the CEFR level (A1, A2, B1, B2, C1, C2).

**Multiple Choice Performance:**
- Total questions: 9
- Correct answers: {correct_count}
- Accuracy: {mc_accuracy * 100:.0f}%

**Free-Text Responses:**
{free_text_str}

**Assessment Criteria:**
- Grammatical accuracy (verb conjugation, case agreement, word order)
- Vocabulary complexity and range
- Sentence structure (simple vs. complex sentences)
- Ability to express opinions and reasons

**Output Format:**
Return ONLY valid JSON (no markdown, no explanation):
{{
  "level": "B1",
  "feedback": "Encouraging, specific feedback in German (1-2 sentences max)",
  "confidence": 0.87
}}
"""
    
    try:
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        # Try to parse JSON from response
        result = json.loads(response_text)
        
    except (json.JSONDecodeError, Exception) as e:
        # Fallback: use MC score to estimate level
        if mc_accuracy > 0.8:
            fallback_level = "B2"
        elif mc_accuracy > 0.6:
            fallback_level = "B1"
        elif mc_accuracy > 0.4:
            fallback_level = "A2"
        else:
            fallback_level = "A1"
        
        result = {
            "level": fallback_level,
            "feedback": "Analyse nicht möglich. Basierend auf MC-Ergebnissen.",
            "confidence": 0.5
        }
    
    return LanguageLevelResponse(**result)
```

- [ ] **Step 2: Register the router in main.py**

Open `backend/src/main.py` and add:

```python
from backend.src.routes import language_level

app.include_router(language_level.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/routes/language_level.py backend/src/main.py
git commit -m "feat(api): add language level analysis endpoint"
```

---

### Task 3: i18n Keys for Diagnosis Modal

**Files:**
- Modify: `frontend/messages/de.json`
- Modify: `frontend/messages/en.json`

- [ ] **Step 1: Add German keys to de.json**

Open `frontend/messages/de.json` and add this section (or extend existing):

```json
{
  "workspace": {
    "detail": {
      "languageTraining": {
        "diagnosis": {
          "title": "Sprachlevel-Test",
          "subtitle": "Kurzer Test, um dein Niveau zu bestimmen. (ca. 5-10 Min)",
          "question": "Frage {{current}} von {{total}}",
          "buttonNext": "Weiter",
          "buttonSubmit": "Prüfen",
          "resultsTitle": "✓ Sprachlevel bestimmt!",
          "resultsLevel": "Dein Niveau",
          "buttonDone": "Fertig",
          "errorTitle": "Fehler",
          "errorMessage": "Fehler beim Speichern. Versuche später erneut.",
          "buttonRetry": "Erneut versuchen"
        }
      }
    }
  }
}
```

- [ ] **Step 2: Add English keys to en.json**

Open `frontend/messages/en.json` and add:

```json
{
  "workspace": {
    "detail": {
      "languageTraining": {
        "diagnosis": {
          "title": "Language Level Test",
          "subtitle": "Quick test to determine your level. (approx. 5-10 min)",
          "question": "Question {{current}} of {{total}}",
          "buttonNext": "Next",
          "buttonSubmit": "Check",
          "resultsTitle": "✓ Language level determined!",
          "resultsLevel": "Your level",
          "buttonDone": "Done",
          "errorTitle": "Error",
          "errorMessage": "Error saving. Try again later.",
          "buttonRetry": "Retry"
        }
      }
    }
  }
}
```

- [ ] **Step 3: Run i18n check**

```bash
npm run check:i18n
```

Expected: No errors about missing keys.

- [ ] **Step 4: Commit**

```bash
git add frontend/messages/de.json frontend/messages/en.json
git commit -m "feat(i18n): add language level diagnosis keys"
```

---

### Task 4: useDiagnosisChat Hook

**Files:**
- Create: `frontend/src/app/[locale]/workspace/[uuid]/_hooks/useDiagnosisChat.ts`

- [ ] **Step 1: Create the hook file**

```typescript
// frontend/src/app/[locale]/workspace/[uuid]/_hooks/useDiagnosisChat.ts
import { useState, useCallback } from "react";

interface DiagnosisMessage {
  id: string;
  type: "question" | "user_answer" | "result";
  questionId: number;
  text: string;
  options?: string[];
  isMultiSelect?: boolean;
}

interface DiagnosisState {
  currentQuestion: number;
  messages: DiagnosisMessage[];
  answers: Map<number, string | string[]>;
  isAnalyzing: boolean;
  error: string | null;
}

export function useDiagnosisChat() {
  const [state, setState] = useState<DiagnosisState>({
    currentQuestion: 1,
    messages: [],
    answers: new Map(),
    isAnalyzing: false,
    error: null,
  });

  const QUESTIONS = [
    {
      id: 1,
      text: "Satzstruktur (Nebensatz): Ich weiß nicht, _______.",
      type: "mc",
      options: ["A) wann der Zug kommt", "B) wann kommt der Zug", "C) kommt der Zug wann"],
      correct: "A) wann der Zug kommt",
    },
    {
      id: 2,
      text: "Perfekt erkennen: Welche Sätze stehen im Perfekt? (Mehrfachauswahl)",
      type: "multi_mc",
      options: [
        "A) Er ist gestern nach Berlin gefahren.",
        "B) Sie liest ein Buch.",
        "C) Wir haben lange telefoniert.",
        "D) Ich werde morgen kochen.",
      ],
      correct: ["A) Er ist gestern nach Berlin gefahren.", "C) Wir haben lange telefoniert."],
    },
    {
      id: 3,
      text: "Präpositionen: Wir warten _____ den Bus.",
      type: "mc",
      options: ["A) auf", "B) an", "C) für"],
      correct: "A) auf",
    },
    {
      id: 4,
      text: "Konjunktionen: Ich bleibe zu Hause, _____ ich krank bin.",
      type: "mc",
      options: ["A) aber", "B) weil", "C) trotzdem"],
      correct: "B) weil",
    },
    {
      id: 5,
      text: "Gegenteile: Was ist das Gegenteil von 'pünktlich'?",
      type: "mc",
      options: ["A) sauber", "B) unpünktlich", "C) müde"],
      correct: "B) unpünktlich",
    },
    {
      id: 6,
      text: "Wortarten: Welche Wörter sind Adjektive? (Mehrfachauswahl)",
      type: "multi_mc",
      options: ["A) Haus", "B) schnell", "C) groß", "D) singen"],
      correct: ["B) schnell", "C) groß"],
    },
    {
      id: 7,
      text: "Synonyme: Welches Wort passt auch für 'höflich'?",
      type: "mc",
      options: ["A) nett", "B) laut", "C) schwierig"],
      correct: "A) nett",
    },
    {
      id: 8,
      text: "Leseverstehen: Das Meeting wurde von 14 Uhr auf 16 Uhr verschoben. Wann findet das Treffen statt?",
      type: "mc",
      options: ["A) Früher als geplant", "B) Später als geplant", "C) Gar nicht"],
      correct: "B) Später als geplant",
    },
    {
      id: 9,
      text: "Situations-Zuordnung: Du bist im Restaurant und möchtest bezahlen. Was sagst du?",
      type: "mc",
      options: ["A) Die Rechnung bitte.", "B) Wo ist der Bahnhof?", "C) Guten Appetit."],
      correct: "A) Die Rechnung bitte.",
    },
    {
      id: 10,
      text: "Bildbeschreibung: Beschreibe in 2 Sätzen: Was siehst du in deinem Zimmer?",
      type: "free_text",
    },
    {
      id: 11,
      text: "E-Mail schreiben: Schreibe eine kurze Entschuldigung an deinen Lehrer, warum du heute nicht kommen kannst.",
      type: "free_text",
    },
    {
      id: 12,
      text: "Meinungsäußerung: Wie findest du das Wetter heute? Warum?",
      type: "free_text",
    },
  ];

  const currentQuestionData = QUESTIONS[state.currentQuestion - 1];

  const addMessage = useCallback((message: DiagnosisMessage) => {
    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, message],
    }));
  }, []);

  const submitAnswer = useCallback(
    (answer: string | string[]) => {
      const msgId = `answer_${state.currentQuestion}`;
      addMessage({
        id: msgId,
        type: "user_answer",
        questionId: state.currentQuestion,
        text: Array.isArray(answer) ? answer.join(", ") : answer,
      });

      const newAnswers = new Map(state.answers);
      newAnswers.set(state.currentQuestion, answer);

      if (state.currentQuestion < QUESTIONS.length) {
        setState((prev) => ({
          ...prev,
          currentQuestion: prev.currentQuestion + 1,
          answers: newAnswers,
        }));
        // Next question will be displayed by component
      } else {
        // All questions answered
        setState((prev) => ({
          ...prev,
          answers: newAnswers,
          currentQuestion: QUESTIONS.length + 1, // trigger results
        }));
      }
    },
    [state.currentQuestion, state.answers, addMessage]
  );

  const reset = useCallback(() => {
    setState({
      currentQuestion: 1,
      messages: [],
      answers: new Map(),
      isAnalyzing: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    currentQuestionData,
    totalQuestions: QUESTIONS.length,
    questions: QUESTIONS,
    submitAnswer,
    addMessage,
    reset,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_hooks/useDiagnosisChat.ts
git commit -m "feat(hooks): add useDiagnosisChat hook for diagnosis state management"
```

---

### Task 5: DiagnosisChat Component

**Files:**
- Create: `frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisChat.tsx`

- [ ] **Step 1: Create DiagnosisChat component**

```typescript
// frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisChat.tsx
"use client";

import React, { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { CaretRight } from "@phosphor-icons/react";

interface DiagnosisChatProps {
  currentQuestion: number;
  totalQuestions: number;
  questionData: {
    id: number;
    text: string;
    type: "mc" | "multi_mc" | "free_text";
    options?: string[];
    isMultiSelect?: boolean;
  } | null;
  messages: Array<{ id: string; type: string; text: string }>;
  onSubmitAnswer: (answer: string | string[]) => void;
  isLoading?: boolean;
}

export function DiagnosisChat({
  currentQuestion,
  totalQuestions,
  questionData,
  messages,
  onSubmitAnswer,
  isLoading = false,
}: DiagnosisChatProps) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [selectedOptions, setSelectedOptions] = React.useState<string[]>([]);
  const [textAnswer, setTextAnswer] = React.useState("");

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Reset form when question changes
  useEffect(() => {
    setSelectedOptions([]);
    setTextAnswer("");
  }, [currentQuestion]);

  const handleOptionClick = (option: string) => {
    if (questionData?.type === "multi_mc") {
      setSelectedOptions((prev) =>
        prev.includes(option) ? prev.filter((o) => o !== option) : [...prev, option]
      );
    } else {
      setSelectedOptions([option]);
    }
  };

  const handleSubmit = () => {
    if (questionData?.type === "free_text") {
      if (textAnswer.trim()) {
        onSubmitAnswer(textAnswer);
      }
    } else {
      if (selectedOptions.length > 0) {
        const answer = questionData?.type === "multi_mc" ? selectedOptions : selectedOptions[0];
        onSubmitAnswer(answer);
      }
    }
  };

  const isAnswerReady =
    (questionData?.type === "free_text" && textAnswer.trim()) ||
    (questionData?.type !== "free_text" && selectedOptions.length > 0);

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-sm border border-border">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border">
        <h2 className="text-lg font-semibold" style={{ color: "var(--foreground)" }}>
          {t("title")}
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          {t("subtitle")}
        </p>
        <div className="mt-3 h-1 bg-surface-dim rounded-full">
          <div
            className="h-1 bg-kb rounded-full transition-all"
            style={{ width: `${(currentQuestion / totalQuestions) * 100}%` }}
          />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {/* Question */}
        {questionData && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-kb text-white flex items-center justify-center shrink-0 text-xs font-bold">
              A
            </div>
            <div className="flex-1">
              <p className="text-sm" style={{ color: "var(--foreground)" }}>
                {questionData.text}
              </p>
              <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>
                {t("question", { current: currentQuestion, total: totalQuestions })}
              </p>
            </div>
          </div>
        )}

        {/* Answer options or input */}
        <div className="flex gap-3">
          <div className="w-8 h-8 rounded-full bg-surface-dim flex-shrink-0" />
          <div className="flex-1 space-y-2">
            {questionData?.type === "free_text" ? (
              <textarea
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                placeholder="Deine Antwort hier..."
                disabled={isLoading}
                className="w-full p-3 rounded-lg border border-border text-sm"
                style={{ color: "var(--foreground)" }}
                rows={4}
              />
            ) : (
              questionData?.options?.map((option, idx) => (
                <button
                  key={idx}
                  onClick={() => handleOptionClick(option)}
                  disabled={isLoading}
                  className={`w-full p-3 rounded-lg border text-left text-sm transition-colors ${
                    selectedOptions.includes(option)
                      ? "bg-kb bg-opacity-10 border-kb"
                      : "border-border hover:border-kb"
                  }`}
                  style={
                    selectedOptions.includes(option)
                      ? { color: "var(--kb)" }
                      : { color: "var(--foreground)" }
                  }
                >
                  {questionData?.type === "multi_mc" && (
                    <input
                      type="checkbox"
                      checked={selectedOptions.includes(option)}
                      readOnly
                      className="mr-2"
                    />
                  )}
                  {option}
                </button>
              ))
            )}
          </div>
        </div>

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-border p-4">
        <button
          onClick={handleSubmit}
          disabled={!isAnswerReady || isLoading}
          className="w-full btn-soft-accent py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-50"
        >
          {currentQuestion === totalQuestions ? t("buttonSubmit") : t("buttonNext")}
          <CaretRight size={14} weight="bold" className="inline ml-0.5" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisChat.tsx
git commit -m "feat(components): add DiagnosisChat component"
```

---

### Task 6: DiagnosisResultsScreen Component

**Files:**
- Create: `frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisResultsScreen.tsx`

- [ ] **Step 1: Create DiagnosisResultsScreen component**

```typescript
// frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisResultsScreen.tsx
"use client";

import React from "react";
import { useTranslations } from "next-intl";

interface DiagnosisResultsScreenProps {
  level: string;
  feedback: string;
  isLoading?: boolean;
  onDone: () => void;
}

export function DiagnosisResultsScreen({
  level,
  feedback,
  isLoading = false,
  onDone,
}: DiagnosisResultsScreenProps) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-sm border border-border p-8">
      <div className="flex-1 flex flex-col items-center justify-center gap-6 text-center">
        <div className="text-5xl">✓</div>

        <div>
          <h2 className="text-2xl font-bold mb-2" style={{ color: "var(--foreground)" }}>
            {t("resultsTitle")}
          </h2>

          <div className="mt-6 p-4 rounded-lg bg-surface-dim">
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {t("resultsLevel")}
            </p>
            <p className="text-4xl font-bold mt-2" style={{ color: "var(--kb)" }}>
              {level}
            </p>
          </div>

          <p className="mt-6 text-sm leading-relaxed" style={{ color: "var(--foreground)" }}>
            {feedback}
          </p>
        </div>
      </div>

      <button
        onClick={onDone}
        disabled={isLoading}
        className="w-full btn-soft-accent py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-50"
      >
        {t("buttonDone")}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/DiagnosisResultsScreen.tsx
git commit -m "feat(components): add DiagnosisResultsScreen component"
```

---

### Task 7: LanguageLevelDiagnosisModal Component

**Files:**
- Create: `frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/LanguageLevelDiagnosisModal.tsx`

- [ ] **Step 1: Create LanguageLevelDiagnosisModal component**

```typescript
// frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/LanguageLevelDiagnosisModal.tsx
"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { DiagnosisChat } from "./DiagnosisChat";
import { DiagnosisResultsScreen } from "./DiagnosisResultsScreen";
import { useDiagnosisChat } from "../_hooks/useDiagnosisChat";

interface LanguageLevelDiagnosisModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLevelDetermined: (level: string) => void;
  userLocale: "de" | "en";
}

export function LanguageLevelDiagnosisModal({
  isOpen,
  onClose,
  onLevelDetermined,
  userLocale,
}: LanguageLevelDiagnosisModalProps) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");
  const {
    currentQuestion,
    totalQuestions,
    currentQuestionData,
    messages,
    answers,
    isAnalyzing,
    error,
    submitAnswer,
    reset,
  } = useDiagnosisChat();

  const [mounted, setMounted] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [resultsData, setResultsData] = useState<{
    level: string;
    feedback: string;
  } | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // When all questions answered, submit to API
  useEffect(() => {
    if (currentQuestion > totalQuestions && !showResults && !isAnalyzing) {
      analyzeLanguageLevel();
    }
  }, [currentQuestion, totalQuestions, showResults, isAnalyzing]);

  const analyzeLanguageLevel = async () => {
    // Build payload
    const mcAnswers = [];
    const freeTextAnswers = [];

    answers.forEach((answer, questionId) => {
      if (questionId <= 9) {
        // MC questions (1-9)
        const selected = Array.isArray(answer) ? answer[0] : answer;
        mcAnswers.push({
          question_id: questionId,
          selected: selected.match(/[A-D]/)?.[0] || selected,
          correct: true, // We'll validate server-side
        });
      } else {
        // Free-text questions (10-12)
        freeTextAnswers.push({
          question_id: questionId,
          answer: Array.isArray(answer) ? answer[0] : answer,
        });
      }
    });

    try {
      const response = await fetch(
        `/api/workspaces/${window.location.pathname.split("/")[3]}/language-level/analyze`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mc_answers: mcAnswers, free_text_answers: freeTextAnswers }),
        }
      );

      if (!response.ok) throw new Error("Analysis failed");

      const data = await response.json();
      setResultsData({ level: data.language_level, feedback: data.feedback });
      setShowResults(true);
    } catch (err) {
      console.error("Analysis error:", err);
      // Fallback result
      setResultsData({
        level: "B1",
        feedback: "Analyse nicht möglich. Bitte später versuchen.",
      });
      setShowResults(true);
    }
  };

  const handleDone = async () => {
    if (resultsData) {
      onLevelDetermined(resultsData.level);
      reset();
      onClose();
    }
  };

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black opacity-50 cursor-not-allowed"
        onClick={(e) => e.preventDefault()}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl h-3/4 max-h-screen mx-4 z-10">
        {showResults && resultsData ? (
          <DiagnosisResultsScreen
            level={resultsData.level}
            feedback={resultsData.feedback}
            isLoading={isAnalyzing}
            onDone={handleDone}
          />
        ) : (
          <DiagnosisChat
            currentQuestion={currentQuestion}
            totalQuestions={totalQuestions}
            questionData={currentQuestionData || null}
            messages={messages}
            onSubmitAnswer={submitAnswer}
            isLoading={isAnalyzing}
          />
        )}
      </div>
    </div>,
    document.body
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/_components/language_training/LanguageLevelDiagnosisModal.tsx
git commit -m "feat(components): add LanguageLevelDiagnosisModal component"
```

---

### Task 8: Integration into Workspace Page

**Files:**
- Modify: `frontend/src/app/[locale]/workspace/[uuid]/page.tsx`

- [ ] **Step 1: Import the modal and add state**

At the top of `page.tsx`, add import:

```typescript
import { LanguageLevelDiagnosisModal } from "./_components/language_training/LanguageLevelDiagnosisModal";
```

- [ ] **Step 2: Add state for diagnosis modal**

In the page component, add state after other useState hooks:

```typescript
const [showDiagnosis, setShowDiagnosis] = useState(false);

// Check on mount if diagnosis should show
useEffect(() => {
  if (workspace?.fachsprachentraining_enabled && !user?.language_level) {
    setShowDiagnosis(true);
  }
}, [workspace?.fachsprachentraining_enabled, user?.language_level]);
```

- [ ] **Step 3: Add modal handler**

Add a function to handle level determination:

```typescript
const handleLanguageLevelDetermined = async (level: string) => {
  // Update user in context/state
  if (user) {
    setUser({ ...user, language_level: level });
  }
  setShowDiagnosis(false);
};
```

- [ ] **Step 4: Render modal in return**

In the JSX return statement, add the modal before closing tags:

```typescript
<LanguageLevelDiagnosisModal
  isOpen={showDiagnosis}
  onClose={() => setShowDiagnosis(false)}
  onLevelDetermined={handleLanguageLevelDetermined}
  userLocale={locale as "de" | "en"}
/>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/[locale]/workspace/[uuid]/page.tsx
git commit -m "feat(integration): add diagnosis modal to workspace page"
```

---

### Task 9: Add Backend Endpoint to Save Language Level

**Files:**
- Modify: `backend/src/routes/user.py` (or similar user routes)

- [ ] **Step 1: Add endpoint to update language_level**

Add this route (in your existing user routes file):

```python
@router.patch("/{user_id}/language-level")
async def update_language_level(
    user_id: int,
    language_level: str,
    db: Session = Depends(get_db),
) -> dict:
    """Update user's language level."""
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if language_level not in valid_levels:
        raise HTTPException(status_code=400, detail="Invalid language level")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.language_level = language_level
    db.commit()
    return {"language_level": user.language_level}
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/routes/user.py
git commit -m "feat(api): add endpoint to update user language level"
```

---

### Task 10: Testing - Happy Path

**Files:**
- Create: `tests/frontend/diagnosis_modal.test.tsx` (or similar)

- [ ] **Step 1: Write test for modal appearance**

```typescript
import { render, screen } from "@testing-library/react";
import { LanguageLevelDiagnosisModal } from "@/app/[locale]/workspace/[uuid]/_components/language_training/LanguageLevelDiagnosisModal";

describe("LanguageLevelDiagnosisModal", () => {
  it("should render modal when isOpen is true", () => {
    render(
      <LanguageLevelDiagnosisModal
        isOpen={true}
        onClose={() => {}}
        onLevelDetermined={() => {}}
        userLocale="de"
      />
    );

    expect(screen.getByText(/Sprachlevel-Test/i)).toBeInTheDocument();
  });

  it("should not render modal when isOpen is false", () => {
    const { container } = render(
      <LanguageLevelDiagnosisModal
        isOpen={false}
        onClose={() => {}}
        onLevelDetermined={() => {}}
        userLocale="de"
      />
    );

    expect(container.querySelector("[role='dialog']")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test**

```bash
npm test -- diagnosis_modal.test.tsx
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/frontend/diagnosis_modal.test.tsx
git commit -m "test: add diagnosis modal tests"
```

---

**All tasks complete!**
