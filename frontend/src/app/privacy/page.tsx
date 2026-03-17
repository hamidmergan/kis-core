import Header from "@/components/Header";

export default function DatenschutzPage() {
  return (
    <>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">Datenschutzerklärung</h1>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">1. Verantwortlicher</h2>
            <p className="text-gray-600">
              Hamid Mergan<br />
              Mönkhofer Weg 239<br />
              23562 Lübeck<br />
              E-Mail: hamid.mergan@th-luebeck.de<br />
              Telefon: +49 451 160818 81
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">
              2. Authentifizierung und Nutzerkonto
            </h2>
            <p className="text-gray-600 mb-2">
              Der Zugang zur Plattform erfolgt über das Hochschulkonto mittels LDAP-Authentifizierung.
              Dabei werden folgende Daten aus dem Verzeichnisdienst der Hochschule übernommen und
              in unserer Datenbank gespeichert:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-1">
              <li>Benutzername (LDAP-Username)</li>
              <li>Anzeigename (vollständiger Name)</li>
              <li>E-Mail-Adresse</li>
            </ul>
            <p className="text-gray-600 mt-2">
              Passwörter werden nicht gespeichert. Die Authentifizierung erfolgt ausschließlich
              über den LDAP-Server der Hochschule.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">
              3. Verarbeitung von Nutzer-Uploads und Job-Daten
            </h2>
            <p className="text-gray-600 mb-2">
              Beim Nutzen der KI-Tools werden hochgeladene Dateien (z.&nbsp;B. Dokumente,
              Audio-Dateien, Präsentationen) sowie die daraus erzeugten Ergebnisse temporär
              gespeichert. Zusätzlich wird für jeden Verarbeitungsauftrag (Job) gespeichert:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-1">
              <li>Genutztes Tool (z.&nbsp;B. Transkription, TTS, Zusammenfassung)</li>
              <li>Ursprünglicher Dateiname</li>
              <li>Zeitpunkt der Erstellung und Fertigstellung</li>
              <li>Verarbeitungsstatus</li>
            </ul>
            <p className="text-gray-600 mt-2">
              Job-Daten und zugehörige Dateien werden nach spätestens{" "}
              <strong>7 Tagen</strong> automatisch gelöscht.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">
              4. Drittanbieter und externe KI-Dienste
            </h2>
            <p className="text-gray-600 mb-2">
              Zur Bereitstellung der KI-Funktionen werden Inhalte an externe Dienste übermittelt:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-1 mb-2">
              <li>
                <strong>ElevenLabs, Inc. (USA)</strong> — Text-to-Speech-Verarbeitung.
                Dabei werden Texteingaben zur Sprachsynthese übermittelt. ElevenLabs ist ein
                US-amerikanischer Anbieter; die Übermittlung erfolgt auf Grundlage von
                Art. 46 DSGVO (Standardvertragsklauseln).
              </li>
              <li>
                <strong>KISSKI / GWDG</strong> — Sprachmodelle und Transkriptionsdienste.
                Dabei werden Texte und Audio-Inhalte verarbeitet. KISSKI ist ein Dienst der
                Gesellschaft für wissenschaftliche Datenverarbeitung mbH Göttingen (GWDG)
                und unterliegt deutschem Datenschutzrecht.
              </li>
            </ul>
            <p className="text-gray-600">
              Es werden nur die für die jeweilige Funktion notwendigen Inhalte übermittelt.
              Keine dauerhafte Speicherung bei den Drittanbietern über die Verarbeitungsdauer hinaus.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">
              5. Server-Logfiles
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
              Diese Daten werden nach spätestens <strong>7 Tagen</strong> automatisch gelöscht.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">6. Rechtsgrundlage</h2>
            <p className="text-gray-600">
              Die Verarbeitung erfolgt auf Grundlage von{" "}
              <strong>Art. 6 Abs. 1 lit. f DSGVO</strong> (berechtigtes Interesse) für
              Server-Logs sowie auf Grundlage von{" "}
              <strong>Art. 6 Abs. 1 lit. b DSGVO</strong> (Vertragserfüllung) für die
              Nutzerdaten und Job-Verarbeitung im Rahmen der Plattformnutzung.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-800 mb-2">7. Ihre Rechte</h2>
            <p className="text-gray-600">
              Sie haben das Recht auf Auskunft, Berichtigung und Löschung Ihrer gespeicherten
              Daten. Bei Fragen wenden Sie sich an:{" "}
              <a href="mailto:hamid.mergan@th-luebeck.de" className="text-blue-600 hover:underline">
                hamid.mergan@th-luebeck.de
              </a>
              . Sie können sich außerdem beim Unabhängigen Landeszentrum für Datenschutz
              Schleswig-Holstein (ULD Kiel) beschweren.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
