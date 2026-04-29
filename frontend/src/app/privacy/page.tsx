export default function DatenschutzPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="bg-white rounded-xl shadow-sm border border-border-soft p-8">
          <h1 className="text-2xl font-bold mb-6">Datenschutzerklärung</h1>

          <p className="text-foreground-soft text-sm mb-6">
            Stand: 29.04.2026
          </p>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">1. Verantwortlicher</h2>
            <p className="text-foreground-soft">
              Hamid Mergan<br />
              Mönkhofer Weg 239<br />
              23562 Lübeck<br />
              E-Mail: hamid.mergan@th-luebeck.de<br />
              Telefon: +49 451 160818 81
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              2. Authentifizierung und Nutzerkonto
            </h2>
            <p className="text-foreground-soft mb-2">
              Der Zugang zur Plattform erfolgt über eine LDAP-Authentifizierung.
              Aktuell wird hierfür ein eigener LDAP-Server genutzt; eine Anbindung
              an den Verzeichnisdienst der Technischen Hochschule Lübeck ist in
              Vorbereitung. Folgende Daten werden in unserer Datenbank gespeichert:
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>Benutzername (LDAP-Username)</li>
              <li>Anzeigename (vollständiger Name)</li>
              <li>E-Mail-Adresse</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              Passwörter werden nicht in dieser Plattform gespeichert. Die
              Authentifizierung erfolgt ausschließlich über den LDAP-Server.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              3. Cookies und lokale Speicherung
            </h2>
            <p className="text-foreground-soft mb-2">
              Diese Plattform verwendet ausschließlich technisch notwendige Cookies und
              Speichermechanismen:
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>
                <strong>Session-Cookie</strong> - Ein HttpOnly-Cookie zur
                Authentifizierung (Gültigkeit: 24&nbsp;Stunden). Ohne dieses
                Cookie ist kein Login möglich.
              </li>
              <li>
                <strong>SessionStorage</strong> - Temporäre Speicherung von
                Filtereinstellungen im Browser (wird beim Schließen des Tabs
                automatisch gelöscht).
              </li>
            </ul>
            <p className="text-foreground-soft mt-2">
              Es werden keine Tracking-, Analyse- oder Marketing-Cookies eingesetzt.
              Es erfolgt keine Weitergabe von Cookie-Daten an Dritte.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              4. Verarbeitung von Nutzer-Uploads und Job-Daten
            </h2>
            <p className="text-foreground-soft mb-2">
              Beim Nutzen der KI-Tools werden hochgeladene Dateien (z.&nbsp;B. Dokumente,
              Audio-Dateien, Präsentationen) sowie die daraus erzeugten Ergebnisse temporär
              gespeichert. Zusätzlich wird für jeden Verarbeitungsauftrag (Job) gespeichert:
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>Genutztes Tool (z.&nbsp;B. Transkription, Zusammenfassung)</li>
              <li>Ursprünglicher Dateiname</li>
              <li>Zeitpunkt der Erstellung und Fertigstellung</li>
              <li>Verarbeitungsstatus</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              Job-Daten und zugehörige Dateien werden nach spätestens{" "}
              <strong>7 Tagen</strong> automatisch gelöscht.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              5. Drittanbieter und externe KI-Dienste
            </h2>
            <p className="text-foreground-soft mb-2">
              Zur Bereitstellung der KI-Funktionen werden Inhalte an externe Dienste übermittelt:
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1 mb-2">
              <li>
                <strong>KISSKI / GWDG</strong> - Sprachmodelle und
                Transkriptionsdienste. Dabei werden Texte und Audio-Inhalte
                verarbeitet. KISSKI ist ein Dienst der Gesellschaft für
                wissenschaftliche Datenverarbeitung mbH Göttingen (GWDG) und
                unterliegt deutschem Datenschutzrecht. Die Verarbeitung erfolgt
                im Rahmen einer Auftragsverarbeitung gemäß Art. 28 DSGVO.
              </li>
            </ul>
            <p className="text-foreground-soft">
              Es werden nur die für die jeweilige Funktion notwendigen Inhalte
              übermittelt. Eine dauerhafte Speicherung bei den Drittanbietern
              über die Verarbeitungsdauer hinaus erfolgt nicht.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              6. Server-Logfiles
            </h2>
            <p className="text-foreground-soft mb-2">
              Beim Aufruf dieser Webseite werden durch den Webserver automatisch
              Informationen in sogenannten Server-Logfiles erfasst. Dies umfasst:
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>IP-Adresse des anfragenden Geräts</li>
              <li>Datum und Uhrzeit des Zugriffs</li>
              <li>Aufgerufene URL und Referrer-URL</li>
              <li>Verwendeter Browser und Betriebssystem</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              Diese Daten werden nach spätestens <strong>7 Tagen</strong> automatisch gelöscht.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">7. SSL-/TLS-Verschlüsselung</h2>
            <p className="text-foreground-soft">
              Die Plattform nutzt zur sicheren Übertragung von Daten eine
              SSL-/TLS-Verschlüsselung. Eine verschlüsselte Verbindung erkennen
              Sie an der Adresszeile des Browsers, die mit &bdquo;https://&ldquo;
              beginnt.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">8. Rechtsgrundlage</h2>
            <p className="text-foreground-soft">
              Die Verarbeitung erfolgt auf Grundlage von{" "}
              <strong>Art. 6 Abs. 1 lit. f DSGVO</strong> (berechtigtes Interesse) für
              Server-Logs sowie auf Grundlage von{" "}
              <strong>Art. 6 Abs. 1 lit. b DSGVO</strong> (Vertragserfüllung) für die
              Nutzerdaten und Job-Verarbeitung im Rahmen der Plattformnutzung.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">9. Ihre Rechte als betroffene Person</h2>
            <p className="text-foreground-soft mb-2">
              Sie haben gegenüber dem Verantwortlichen folgende Rechte hinsichtlich
              der Sie betreffenden personenbezogenen Daten:
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>Recht auf Auskunft (Art. 15 DSGVO)</li>
              <li>Recht auf Berichtigung (Art. 16 DSGVO)</li>
              <li>Recht auf Löschung (Art. 17 DSGVO)</li>
              <li>Recht auf Einschränkung der Verarbeitung (Art. 18 DSGVO)</li>
              <li>Recht auf Datenübertragbarkeit (Art. 20 DSGVO)</li>
              <li>Recht auf Widerspruch gegen die Verarbeitung (Art. 21 DSGVO)</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              Zur Ausübung dieser Rechte wenden Sie sich an:{" "}
              <a href="mailto:hamid.mergan@th-luebeck.de" className="text-info hover:underline">
                hamid.mergan@th-luebeck.de
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">10. Beschwerderecht</h2>
            <p className="text-foreground-soft">
              Sie haben das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu
              beschweren. Zuständig ist das{" "}
              <strong>
                Unabhängige Landeszentrum für Datenschutz Schleswig-Holstein
                (ULD Kiel)
              </strong>
              .
            </p>
          </section>
        </div>
    </div>
  );
}
