import Header from "@/components/Header";

export default function DatenschutzPage() {
  return (
    <>
      <Header />
      <div className="max-w-2xl mx-auto px-4 py-10">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">Datenschutzerklärung</h1>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">1. Verantwortlicher</h2>
            <p className="text-gray-600">
              Hamid Mergan<br />
              Mönkhofer Weg 239<br />
              23562 Lübeck<br />
              E-Mail: hamid.mergan@gmail.com<br />
              Telefon: +49 451 160818 81
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">
              2. Erhebung und Speicherung personenbezogener Daten
            </h2>
            <p className="text-gray-600 mb-2">
              Beim Aufruf dieser Webseite werden durch den Webserver automatisch
              Informationen in sogenannten Server-Logfiles erfasst. Dies umfasst:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-1">
              <li>IP-Adresse des anfragenden Geräts</li>
              <li>Datum und Uhrzeit des Zugriffs</li>
              <li>Aufgerufene URL und Referrer-URL</li>
              <li>Verwendeter Browser und Betriebssystem</li>
            </ul>
            <p className="text-gray-600 mt-2">
              Diese Daten werden ausschließlich zur Sicherstellung eines
              störungsfreien Betriebs und zur Verbesserung der Sicherheit
              unserer Systeme verarbeitet.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">3. Rechtsgrundlage</h2>
            <p className="text-gray-600">
              Die Verarbeitung erfolgt auf Grundlage von{" "}
              <strong>Art. 6 Abs. 1 lit. f DSGVO</strong> (berechtigtes Interesse).
              Unser berechtigtes Interesse liegt in der Bereitstellung und
              Absicherung dieses Webdienstes.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-800 mb-2">4. Speicherdauer</h2>
            <p className="text-gray-600">
              Die Server-Logfiles einschließlich der IP-Adressen werden nach
              spätestens <strong>7 Tagen</strong> automatisch gelöscht, sofern
              keine weitergehende Aufbewahrung zu Beweiszwecken erforderlich ist.
              Sie haben das Recht auf Auskunft sowie Löschung Ihrer Daten und
              können sich beim ULD Kiel beschweren.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
