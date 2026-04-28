import Link from "next/link";
import Header from "@/components/layout/Header";

export default function TestphasePage() {
  return (
    <>
      <Header />
      <div className="flex items-center justify-center min-h-[70vh] px-4">
        <div className="w-full max-w-lg">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center">
                <svg
                  className="w-8 h-8 text-yellow-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                  />
                </svg>
              </div>
            </div>

            <h1 className="text-xl font-bold mb-2">
              Konto noch nicht freigeschaltet
            </h1>

            <p className="text-gray-600 mb-4">
              KIS befindet sich derzeit in der Testphase. Ihr TH-Lübeck-Konto
              wurde erfolgreich erkannt, ist aber noch nicht für die Nutzung
              freigegeben.
            </p>

            <p className="text-gray-600 mb-6">
              Wenn Sie Zugang zu KIS benötigen, wenden Sie sich bitte an:
            </p>

            <a
              href="mailto:hamid.mergan@th-luebeck.de"
              className="inline-block px-4 py-2 btn-primary text-sm font-medium rounded-md  transition-colors mb-6"
            >
              hamid.mergan@th-luebeck.de
            </a>

            <div>
              <Link
                href="/login"
                className="text-sm text-primary hover:underline"
              >
                Zurück zur Anmeldung
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
