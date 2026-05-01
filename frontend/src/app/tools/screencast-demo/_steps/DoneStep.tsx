interface DoneStepProps {
  videoUrl: string | null;
  audioId: string;
  onDownloadMp4: () => void;
  onReset: () => void;
}


export function DoneStep({ videoUrl, audioId, onDownloadMp4, onReset }: DoneStepProps) {
  const handleZipDownload = () => {
    const endpoint = audioId ? `/api/jobs/${audioId}/bundle` : "/api/screencast-demo/bundle";
    const a = document.createElement("a");
    a.href = endpoint;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-8">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-success-bg flex items-center justify-center">
          <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold mb-2 text-center">Fertig! Ihr Screencast ist bereit.</h2>

      {videoUrl && (
        <div className="mb-6 rounded-lg overflow-hidden border border-border-soft">
          <video key={videoUrl} controls className="w-full">
            <source src={videoUrl} type="video/mp4" />
            Ihr Browser unterstützt kein HTML5-Video.
          </video>
        </div>
      )}

      <div className="flex justify-center gap-3 mb-4">
        <button onClick={onDownloadMp4} aria-label="MP4"
          className="px-6 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          MP4
        </button>
        <button onClick={handleZipDownload} aria-label="Alles herunterladen (ZIP)"
          className="px-6 py-2 bg-background text-kb border-2 border-kb text-sm font-medium rounded-md hover:border-kb-dark transition-colors flex items-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Alles herunterladen (ZIP)
        </button>
      </div>

      <div className="flex justify-center">
        <button onClick={onReset} aria-label="Neue Präsentation hochladen"
          className="px-6 py-2 text-sm text-error border-2 border-error-border rounded-md hover:border-error transition-colors">
          Neue Präsentation
        </button>
      </div>
    </section>
  );
}
