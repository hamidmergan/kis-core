"use client";

import { useRef } from "react";
import { PDFViewer, type PDFViewerRef } from "@embedpdf/react-pdf-viewer";

export default function EmbedPdfTestPage() {
  const viewerRef = useRef<PDFViewerRef>(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <div
        style={{
          padding: "12px 20px",
          background: "var(--kb)",
          color: "#fff",
          fontSize: 14,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <strong>EmbedPDF PoC</strong> — Doppelklick auf &quot;Risiken&quot; (S.
        14) und &quot;KINTERNATIONALISIERUNG&quot; (S. 1) testen
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <PDFViewer
          ref={viewerRef}
          config={{
            src: "/test-antrag.pdf",
            worker: true,
          }}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}
