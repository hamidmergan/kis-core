// Quiz-Modal Konfiguration - einfache Modals
const quizModals = [
    {
        id: 'Frage', title: 'Quiz 1', bodyClass: 'mt-3',
        content: {
            type: 'radio',
            question: 'Welche Lernplattform nutzt die TH Lübeck?',
            options: [
                { text: 'Stud.IP', correct: false },
                { text: 'Lernraum', correct: true },
                { text: 'Studierendenportal', correct: false },
                { text: 'Moodle', correct: false }
            ]
        },
        campusInfo: { text: 'Die TH Lübeck benutzt für die Organisation im Semester die auf Moodle basierende Plattform „Lernraum". Dort kannst du dich in deine Kurse einschreiben und während des Semesters alle Informationen und Inhalte abrufen.', link: { url: 'https://www.th-luebeck.de/studium/studierende/lernplattformen/', text: 'Mehr zum Lernraum an der TH Lübeck' } }
    },
    {
        id: 'Frage2', title: 'Quiz 2', bodyClass: 'mt-1',
        description: 'Memory - Finde die Sportangebote der TH Lübeck',
        content: {
            type: 'memory',
            // Jeder Eintrag erscheint zweimal als Karte und muss als Paar gefunden werden.
            pairs: [
                { image: 'assets/welche_sportarten_gibt_es_drachenboot.png', label: 'Drachenboot' },
                { image: 'assets/welche_sportarten_gibt_es_judo.png', label: 'Judo' },
                { image: 'assets/welche_sportarten_gibt_es_k_pop.png', label: 'K-Pop' },
                { image: 'assets/welche_sportarten_gibt_es_tuchakrobatik.png', label: 'Tuchakrobatik' },
                { image: 'assets/welche_sportarten_gibt_es_unterwasserrugby.png', label: 'Unterwasserrugby' },
                { image: 'assets/welche_sportarten_gibt_es_volleyball.png', label: 'Volleyball' }
            ]
        },
        campusInfo: { text: 'Du interessierst dich für Sport und Bewegung neben dem Studium? Dann bietet dir der Hochschulsport vielfältige Möglichkeiten, fit zu bleiben und neue Sportarten auszuprobieren.', link: { url: 'https://www.hochschulsport-luebeck.de/', text: 'Zum Hochschulsport Lübeck' } }
    },
    {
        id: 'Frage3', title: 'Quiz 3',
        content: {
            type: 'checkbox',
            question: 'Was soll das Logo der THL darstellen?',
            options: [
                { text: 'Das Holstentor', correct: false },
                { text: 'Das Auge Saurons', correct: false },
                { text: 'Ein abstraktes Erkennungszeichen', correct: true },
                { text: 'Die Sonne über der Ostsee', correct: false }
            ],
            successMessage: 'Richtig! Das Logo ist kein konkretes Symbol, sondern ein abstraktes Erkennungszeichen.'
        },
        campusInfo: { text: 'Das Logo ist kein konkretes Symbol, sondern ein abstraktes Erkennungszeichen der Technischen Hochschule Lübeck.', link: { url: 'https://www.th-luebeck.de/', text: 'Zur Website der TH Lübeck' } }
    },
    {
        id: 'Frage4', title: 'Quiz 4',
        content: {
            type: 'sort',
            question: 'Bringe die Schritte einer Studienbewerbung an der THL in die richtige Reihenfolge:',
            // Reihenfolge unten = korrekte Reihenfolge (wird beim Rendern gemischt)
            items: [
                'Ich registriere mich beim THL Bewerbungsportal',
                'Ich gebe meine persönlichen Daten ein',
                'Ich gebe an, für welchen Studiengang ich mich bewerben möchte',
                'Ich reiche meine Hochschulzugangsberechtigung im Online-Portal ein',
                'Ich gebe meine Bewerbung im Online-Portal ab'
            ]
        },
        campusInfo: { text: 'Du hast Interesse an einem Studium an der Technischen Hochschule Lübeck? Dann läuft deine Bewerbung ganz einfach online über unser Bewerbungsportal. Alle Schritte findest du hier:', link: { url: 'https://www.th-luebeck.de/studium/bewerbung/schritt-fuer-schritt-erklaert/', text: 'Schritt-für-Schritt-Anleitung der TH Lübeck' } }
    },
    {
        id: 'Frage5', title: 'Quiz 5',
        content: {
            type: 'wordsearch',
            question: 'Finde alle Begriffe rund um das Studentenleben an der TH Lübeck:',
            width: 14, height: 14,
            // display = was in der Liste angezeigt wird; search = was tatsächlich im Raster steht
            words: [
                { display: 'Wohnheim', search: 'WOHNHEIM' },
                { display: 'AStA', search: 'ASTA' },
                { display: 'Klokurier', search: 'KLOKURIER' },
                { display: 'COAL Festival', search: 'COAL' },
                { display: 'Erasmus', search: 'ERASMUS' },
                { display: 'TH Chor', search: 'CHOR' },
                { display: 'Stressbar', search: 'STRESSBAR' },
                { display: 'Hochschulgaming', search: 'GAMING' },
                { display: 'BAföG', search: 'BAFOEG' },
                { display: 'Stipendien', search: 'STIPENDIEN' }
            ]
        },
        campusInfo: { hasAccordion: true, accordionItems: [{ id: 'wohnheim', title: 'Wohnheim', text: 'Infos zum Studentenwohnheim in Lübeck findest du beim', link: { url: 'https://studentenwerk.sh/de/wohnheime-luebeck', text: 'Studentenwerk Schleswig-Holstein' } }, { id: 'asta', title: 'AStA', text: 'Der Allgemeine Studierendenausschuss vertritt deine Interessen und organisiert viele Events. Mehr Infos:', link: { url: 'https://www.th-luebeck.de/gremien-thl/gremien/asta', text: 'AStA TH Lübeck' } }, { id: 'klokurier', title: 'Klokurier', text: 'Die Studierendenzeitung der TH Lübeck:', link: { url: 'https://www.th-luebeck.de/gremien-thl/gremien/hochschulgruppen/klokurier/', text: 'Klokurier Website' } }, { id: 'coal', title: 'COAL Festival', text: 'Das Campus Open Air Lübeck - das größte Festival der Lübecker Hochschulen:', link: { url: 'https://coaluebeck.de', text: 'COAL Festival' } }, { id: 'erasmus', title: 'Erasmus', text: 'Austauschstudium mit Erasmus+: Infos beim', link: { url: 'https://www.th-luebeck.de/en/studies/study-offer/international-students/', text: 'International Office TH Lübeck' } }, { id: 'chor', title: 'TH Chor', text: 'Der Hochschulchor Lübeck bietet musikalische Gemeinschaft und Auftritte. Infos:', link: { url: 'https://www.th-luebeck.de/gremien-thl/gremien/hochschulgruppen/th-chor/', text: 'Hochschulchor' } }, { id: 'stressbar', title: 'Stressbar', text: 'Die legendäre Studierendenbar „Stress" am Campus Lübeck. Mehr Infos:', link: { url: 'https://www.th-luebeck.de/gremien-thl/studentisches-leben/nachtleben/studentisch-gefuehrte-kneipen/stress/', text: 'Stress Bar' } }, { id: 'gaming', title: 'Hochschulgaming Lübeck', text: 'Die Gaming-Community an der TH Lübeck organisiert Turniere und Treffen. Mehr Infos:', link: { url: 'https://www.th-luebeck.de/gremien-thl/gremien/hochschulgruppen/hsgl-hochschulgamingluebeck/', text: 'Hochschulgaming Lübeck' } }, { id: 'bafoeg', title: 'BAföG', text: 'Infos zur Studienfinanzierung durch BAföG bei der', link: { url: 'https://www.th-luebeck.de/studium/studienstart/foerderung-und-stipendien/uebersicht/bafoeg/', text: 'TH Lübeck' } }, { id: 'stipendien', title: 'Stipendien', text: 'Verschiedene Stipendien wie Deutschlandstipendium oder fachspezifische Förderungen:', link: { url: 'https://www.th-luebeck.de/studium/studienstart/foerderung-und-stipendien/deutschlandstipendium/', text: 'Infos zu Stipendien' } }] } },
    {
        id: 'Frage6', title: 'Quiz 6',
        content: {
            type: 'imageGrid',
            question: 'Welche zwei Studiengänge werden NICHT an der TH Lübeck angeboten?',
            columns: 3,
            // correct: true = Studiengang wird NICHT angeboten (richtige Antwort, anklicken)
            options: [
                { image: 'assets/01_bauingenieurwesen.png', label: 'Bauingenieurwesen', correct: false },
                { image: 'assets/02_game_design.png', label: 'Game Design', correct: true },
                { image: 'assets/03_hoerakustik.png', label: 'Hörakustik', correct: false },
                { image: 'assets/04_informatik.png', label: 'Informatik', correct: false },
                { image: 'assets/05_biomedizintechnik.png', label: 'Biomedizintechnik', correct: false },
                { image: 'assets/06_it-sicherheit.png', label: 'IT-Sicherheit', correct: false },
                { image: 'assets/07_maschinenbau.png', label: 'Maschinenbau', correct: false },
                { image: 'assets/08_international_management.png', label: 'International Management', correct: true },
                { image: 'assets/09_architektur.png', label: 'Architektur', correct: false }
            ]
        },
        campusInfo: { text: 'Die Technische Hochschule Lübeck bietet eine große Auswahl an Studiengängen in Technik, Naturwissenschaften, Bauwesen und Wirtschaft. Es gibt Bachelor- und Masterabschlüsse, viele davon auch in Online- oder dualen Formaten.', link: { url: 'https://www.th-luebeck.de/studium/studienangebot/studiengaenge', text: 'Alle Studiengänge im Überblick – TH Lübeck' } }
    },
    {
        id: 'Frage7', title: 'Quiz 7', bodyClass: 'mt-3',
        content: {
            type: 'checkbox',
            question: 'Welche Möglichkeiten gibt es, sich besser für ein Studium an der THL zu orientieren?',
            options: [
                { text: 'Studierenden über die Studienlotsen bei einem Hochschultag begleiten', correct: true },
                { text: 'Einen Termin bei der Studien(fach)beratung vereinbaren', correct: true },
                { text: 'Ein Schnupperstudium oder Orientierungssemester absolvieren', correct: true },
                { text: 'Die Fachschaft des interessierten Studiengangs kontaktieren', correct: true }
            ]
        },
        campusInfo: { hasMultipleLinks: true, items: [{ text: 'Sich für ein Studium zu entscheiden, kann eine große Herausforderung darstellen. Deshalb wollen wir Dich auf diesem Weg bestmöglich unterstützen. Infos zur persönlichen Beratung findest Du hier:', link: { url: 'https://www.th-luebeck.de/studium/studienorientierung/persoenliche-beratung/', text: 'Persönliche Beratung | Technische Hochschule Lübeck' } }, { text: 'sowie Angebote für Schüler:innen und Studieninteressierte hier:', link: { url: 'https://www.th-luebeck.de/studium/studienorientierung/studienorientierung-fuer-schueler-innen-und-studieninteressierten/', text: 'Orientierungsangebote für Schüler*innen und Studieninteressierte' }, className: 'mt-3' }] }
    },
    {
        id: 'Frage8', title: 'Quiz 8', bodyClass: 'mt-3',
        content: {
            type: 'hotspot',
            question: 'Was fehlt für einen sicheren Laborversuch? Klicke alle Sicherheitsmängel an.',
            image: 'assets/labor.png',
            // Textalternative fürs Suchbild: beschreibt die Szene, verrät aber
            // die Mängel nicht (WCAG 1.1.1, Ausnahme für Tests/Übungen)
            imageAlt: 'Suchbild: Studierende arbeiten an einer Laborbank mit Pipetten, Proben und einer Zentrifuge.',
            // x,y in %, radius in % der Bildbreite
            // debug: true blendet die Hotspot-Zonen als gestrichelte Kreise ein (nur zum Justieren)
            debug: false,
            hotspots: [
                { x: 30.4, y: 56.9, radius: 7, label: 'Essen im Labor' },
                { x: 46.5, y: 95.2, radius: 7, label: 'Verschüttete Probe' },
                { x: 47.5, y: 33.8, radius: 6, label: 'Keine Schutzbrille' },
                { x: 67.6, y: 30.2, radius: 6, label: 'Keine Schutzbrille (2. Person)' },
                { x: 86.6, y: 64.0, radius: 11, label: 'Kein Laborkittel' }
            ]
        },
        campusInfo: { text: 'An der TH wird Praxis groß geschrieben. Hier eignest du dir nicht nur Wissen an, sondern kannst es in verschiedenen Praktika auch direkt anwenden.' }
    },
    {
        id: 'Frage9', title: 'Quiz 9',
        content: {
            type: 'radio',
            question: 'Um wie viel Uhr macht die Zentrale Hochschulbibliothek in der Regel auf?',
            options: [
                { text: '9:00 Uhr', correct: true },
                { text: '8:00 Uhr', correct: false },
                { text: '11:30 Uhr', correct: false },
                { text: '7:15 Uhr', correct: false }
            ]
        },
        campusInfo: { text: 'Die ZHB ist ein toller Ort zum Lernen oder Recherchieren. Hier gibt es nicht nur viele Bücher, sondern auch mehrere Einzel- und Gruppenarbeitstische sowie buchbare Räume. Wenn du die Bibliothek einmal nicht besuchen möchtest, kannst du über die Fernleihe zahlreiche Bücher bequem von Zuhause aus online aufrufen.', link: { url: 'https://www.zhb.uni-luebeck.de/', text: 'Mehr Informationen zur ZHB' } }
    },
    {
        id: 'Frage10', title: 'Quiz 10',
        content: {
            type: 'crossword',
            question: 'Welche Studienbegriffe sind gesucht?',
            words: [
                { answer: 'MENSA', clue: 'Kantine für Studierende' },
                { answer: 'PROFESSOR', clue: 'Hochschullehrende:r' },
                { answer: 'VORLESUNG', clue: 'Lehrveranstaltung' },
                { answer: 'HÖRSAAL', clue: 'Raum für Vorlesungen' },
                { answer: 'KLAUSUR', clue: 'Prüfung am Ende des Semesters' },
                { answer: 'BACHELOR', clue: 'Erster akademischer Grad' },
                { answer: 'CAMPUS', clue: 'Universitätsgelände' },
                { answer: 'BAFÖG', clue: 'Staatliche Studienförderung' },
                { answer: 'SEMESTER', clue: 'Halbjahr im Studium' },
                { answer: 'AUDIMAX', clue: 'Größter Hörsaal einer Hochschule' }
            ]
        },
        campusInfo: { text: 'Wenn dich das Rätsel neugierig gemacht hat, findest du auf der Website der Technischen Hochschule Lübeck weitere Tipps und Angebote für Studieninteressierte.', link: { url: 'https://www.th-luebeck.de/studium/studienorientierung/studienorientierung-fuer-schueler-innen-und-studieninteressierten/', text: 'Zur Studienorientierung an der TH Lübeck' } }
    }
];

/**
 * Campus Gebäude Konfiguration
 * 
 * Mögliche Parameter pro Gebäude:
 * - id: string (erforderlich) - Eindeutige ID
 * - title: string (erforderlich) - Anzeigename
 * - icon: string - Pfad zum Icon
 * - iconHeight: string - CSS-Höhe für Icon (z.B. "90px")
 * - images: array - Array von Bildpfaden
 * - description: string - Beschreibungstext (HTML erlaubt)
 * - featureSections: array - Zusätzliche Informationssektionen
 *   - { heading: string, color: string, items: array }
 * - openingHours: object - Öffnungszeiten
 *   - { label: string, bgColor: string, color: string, slots: array }
 *   - slots: { label: string, time: string }
 * - link: object - Externer Link
 *   - { title: string, url: string, text: string }
 */
const campusBuildings = [
    {
        id: "Mensa_B_59",
        title: "Mensa B.59",
        icon: "assets/gebaeude_B_59_mensa.svg",
        images: [
            "assets/gebaeude_B_1_mensa_01.jpg",
            "assets/gebaeude_B_1_mensa_02.jpg",
            "assets/gebaeude_B_1_mensa_03.jpg",
            "assets/gebaeude_B_1_mensa_04.jpg",
            "assets/gebaeude_B_1_mensa_05.jpg"
        ],
        description: "Die Mensa befindet sich auf dem Campus neben Bibliothek und Audimax und bietet täglich drei bis vier frische Gerichte, darunter mindestens ein vegetarisches. Neben täglich wechselnden Angeboten erwartet dich in der Mensa auch eine Auswahl an Desserts. <br><br>Für Kinder stehen Kinderstühle, eine Spielecke und ein Wickeltisch zur Verfügung.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#63b4b8",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "11:15 - 14:15 Uhr" },
                { label: "Zero Waste Teller:", time: "14:15 - 14:30 Uhr" },
                { label: "Vorlesungsfreie Zeit:", time: "11:15 - 13:30 Uhr" }
            ]
        }
    },
    {
        id: "Audimax_B_65",
        title: "Audimax B.65",
        icon: "assets/gebaeude_B_65_audimax.svg",
        images: [
            "assets/gebaeude_B_3_audimax_01.jpg",
            "assets/gebaeude_B_3_audimax_02.jpg",
            "assets/gebaeude_B_3_audimax_03.jpg",
            "assets/gebaeude_B_3_audimax_04.jpg",
            "assets/gebaeude_B_3_audimax_05.jpg"
        ],
        description: "Das Audimax ist das zentrale Hörsaalzentrum auf dem Campus der Technischen Hochschule Lübeck und der Universität zu Lübeck. Es beherbergt mit dem Hörsaal AM 1 einen großen Vortragssaal, ausgestattet mit umfassender Medientechnik und speziellen Einrichtungen für musikalische Veranstaltungen. <br>Und zwei weitere Säle, AM 2 und AM 3, bieten moderne Ausstattung für Vorlesungen und Seminare. <br><br>Das Audimax wird regelmäßig für Veranstaltungen wie Vorträge, Karrieretage oder Festivalprogramme genutzt.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#63b4b8",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Bibliothek_B_60",
        title: "Bibliothek B.60",
        icon: "assets/gebaeude_B_60_bibliothek.svg",
        images: [
            "assets/gebaeude_B_2_bibliothek_01.jpg",
            "assets/gebaeude_B_2_bibliothek_02.jpg"
        ],
        description: "Die Zentrale Hochschulbibliothek Lübeck ist eine gemeinsame wissenschaftliche Einrichtung der Technischen Hochschule Lübeck und der Universität zu Lübeck. Sie versorgt die Hochschulangehörigen mit aktueller Literatur aus den Bereichen Medizin, Technik, Informatik, Naturwissenschaften, Wirtschaft und Bauwesen. <br><br>Räumlich ist hier zu finden ein PC-Pool, ein Ruhearbeitsraum und spezielle Arbeitsräume für blinde und sehbehinderte Nutzerinnen und Nutzer, Gruppenarbeitsräume, sowie eine Studi-Lounge mit 20 Plätzen.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#63b4b8",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "09:00 - 22:30 Uhr (Ausleihe über die Leihstelle: 09:00 - 18:00)" },
                { label: "Sa:", time: "09:00 - 20:00 Uhr (Leihstelle: 09:00 - 13:00)" },
                { label: "So:", time: "10:00 - 20:00 Uhr (nur Ausleihe via Automat)" }
            ]
        }
    },

    {
        id: "Gebaeude_B_64",
        title: "Gebäude B.64",
        icon: "assets/gebaeude_B_64.svg",
        images: [
            "assets/gebaeude_B_4_01.jpg",
            "assets/gebaeude_B_4_02.jpg"
        ],
        description: "Im Gebäude B.64 befindet sich das Laborgebäude Biomedizintechnik AN und das Kompetenzzentrum TANDEM (Technology and Engineering in Medicine). <br><br>Es beherbergt zusätzlich zahlreiche Institute der Universität zu Lübeck wie das Institut für Technische Informatik, das Institut für Neuro- und Bioinformatik, das Institut für Informationssysteme, das Institut für IT-Sicherheit, das IT-Service-Center sowie IMIS (Institut für Multimediale und Interaktive Systeme)."
    },


    {
        id: "MFC_7",
        title: "MFC 7",
        icon: "assets/gebaeude_MFC_7.svg",
        images: [
            "assets/gebaeude_MFC_7_01.jpg",
            "assets/gebaeude_MFC_7_02.jpg",
            "assets/gebaeude_MFC_7_03.jpg"
        ],
        description: "Im MFC VII (Multifunktionscenter 7) an der Maria-Goeppert-Straße 9 befindet sich unter anderem das Institut für Interaktive Systeme (ISy) der TH Lübeck, das wegweisende Forschung in den Bereichen digitale Bildung, Learning Analytics, KI und Human-Centered Design betreibt und zahlreiche Drittmittelprojekte durchführt. <br><br> Ebenfalls im MFC VII angesiedelt ist das Zentrum für Digitale Lehre (ZDL), das Lehrende bei digital gestützter Hochschullehre unterstützt.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#b7bcc5",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 18:00 Uhr" }
            ]
        }
    },

    {
        id: "MFC_8",
        title: "MFC 8",
        icon: "assets/gebaeude_MFC_8.svg",
        images: [
            "assets/gebaeude_MFC_8_03.jpg",
            "assets/gebaeude_MFC_8_02.jpg",
            "assets/gebaeude_MFC_8_01.jpg"
        ],
        description: "Im MFC VIII (Multifunktionscenter 8) an der Maria-Goeppert-Straße 9a befindet sich das FabLab Lübeck, eine offene High-Tech-Werkstatt für Prototyping mit 3D-Druck, Laser-Cutter und CNC-Maschinen.<br><br>Auch befindet sich in diesem Gebäude das Institut für Psychologie I (IPSY I) der Universität zu Lübeck.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#b7bcc5",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 18:00 Uhr" }
            ]
        }
    },

    {
        id: "MFC_1",
        title: "MFC 1",
        icon: "assets/gebaeude_MFC_1.svg",
        images: [
            "assets/gebaeude_MFC_1_01.jpg",
            "assets/gebaeude_MFC_1_02.jpg",
            "assets/gebaeude_MFC_1_03.jpg"
        ],
        description: "Das MFC I (Multifunktionscenter 1) an der Maria-Goeppert-Straße 1 ist ein Bürogebäude, unweit vom Carlebach-Park gelegen. <br><br>In diesem Gebäude befindet sich unter anderem das Technikzentrum Lübeck (TZL) und das Campus Taste.",
        openingHours: {
            label: "Öffnungszeiten Büro- und Verwaltungszeiten für das Technikzentrum Lübeck (TZL)",
            bgColor: "#b7bcc5",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "08:00 - 16:00 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_G_1",
        title: "Gebäude G.1",
        icon: "assets/gebaeude_G_1.svg",
        images: [
            "assets/gebaeude_G_1_01.jpg",
            "assets/gebaeude_G_1_02.jpg",
            "assets/gebaeude_G_1_03.jpg",
            "assets/gebaeude_G_1_04.jpg",
            "assets/gebaeude_G_1_05.jpg"
        ],
        description: "Gebäude G.1 ist ein Laborgebäude des Fachbereichs Angewandte Naturwissenschaften (AN). Hier befinden sich auch das Sekretariat des Fachbereichs AN und das Centrum Industrielle Biotechnologie (CIB).",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#b57393",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_G_2",
        title: "Gebäude G.2",
        icon: "assets/gebaeude_G_2.svg",
        images: [
            "assets/gebaeude_G_2_01.jpg",
            "assets/gebaeude_G_2_02.jpg",
            "assets/gebaeude_G_2_03.jpg",
            "assets/gebaeude_G_2_04.jpg"
        ],
        description: "Gebäude G.2 ist ein Laborgebäude der Fachbereiche Angewandte Naturwissenschaften (AN) und Maschinenbau und Wirtschaft (MW). Hier gibt es außerdem einen Still- und Wickelraum.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#b57393",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_G_3",
        title: "Gebäude G.3",
        icon: "assets/gebaeude_G_3.svg",
        images: [
            "assets/gebaeude_G_3_01.jpg",
            "assets/gebaeude_G_3_02.jpg",
            "assets/gebaeude_G_3_03.jpg",
            "assets/gebaeude_G_3_04.jpg"
        ],
        description: "Gebäude G.3 ist ein Laborgebäude des Fachbereichs Elektrotechnik und Informatik (EI). <br>Im zweiten Obergeschoss befindet sich das Kompetenzzentrum CoSA (Kommunikation-Systeme-Anwendungen) des Fachbereichs Elektrotechnik und Informatik.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#b57393",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },
    {
        id: "GruenderCube_1",
        title: "GründerCube 1",
        icon: "assets/gruender_cube_1.svg",
        images: [
            "assets/gruender_cube_1_01.jpg",
            "assets/gruender_cube_1_02.jpg"
        ],
        description: "Der GründerCube 1 ist eine gemeinsame Gründungsberatungseinrichtung der Technischen Hochschule Lübeck und der Universität zu Lübeck. <br><br>Er unterstützt Studierende, Wissenschaftler und Alumni von der Ideenfindung bis zur Gründung eines Start-ups mit Beratung, Workshops, Veranstaltungen und einem breiten Netzwerk.",
    },
    {
        id: "GruenderCube_2",
        title: "GründerCube 2",
        icon: "assets/gruender_cube_2.svg",
        images: [
            "assets/gruender_cube_2_01.jpg",
            "assets/gruender_cube_2_02.jpg"
        ],
        description: "Der GründerCube 2 erweitert das Gründungszentrum. <br><br>Das flexibel konzipierte Modul ergänzt den ersten Cube um fast 98 m² zusätzliche Fläche, u.a. mit Beratungs- und Arbeitsräumen, ideal für die individuelle Projektarbeit und Gründungsberatung in einem ruhigen Umfeld.",
    },
    {
        id: "Gebaeude_E_5",
        title: "Gebäude E.5",
        icon: "assets/gebaeude_E_5.svg",
        iconHeight: "90px",
        images: [
            "assets/gebaeude_E_5_01.jpg",
            "assets/gebaeude_E_5_02.jpg",
            "assets/gebaeude_E_5_03.jpg",
            "assets/gebaeude_E_5_04.jpg"
        ],
        description: "Im Gebäude E.5 befinden sich Teile der Hochschulverwaltung sowie das Büro des Betriebsarztes. Das Gebäude ist nicht ebenerdig zugänglich und hat keinen Aufzug."
    },

    {
        id: "Gebaeude_E_4",
        title: "Gebäude E.4",
        icon: "assets/gebaeude_E_4.svg",
        iconHeight: "90px",
        images: [
            "assets/gebaeude_E_4_01.jpg",
            "assets/gebaeude_E_4_02.jpg"
        ],
        description: "Das Gebäude E.4 beherbergt die Fachschaft für Angewandte Naturwissenschaften (FS AN), die Fachschaft Bauwesen (FS BAU) und die Fachschaft Technik und Wirtschaft (FS TW), welche die Studierenden in studentischen Angelegenheiten unterstützt. <br><br>Des Weiteren befinden sich in diesem Gebäude das Studierendenparlament (StuPa) sowie der AStA (Allgemeine Studierendenausschuss).",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8197b9",
            color: "#212529",
            slots: [
                { label: "Di u. Do:", time: "13:15 - 14:00 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_E_3",
        title: "Gebäude E.3",
        icon: "assets/gebaeude_E_3.svg",
        iconHeight: "130px",
        images: [
            "assets/gebaeude_E_3_01.jpg",
            "assets/gebaeude_E_3_02.jpg"
        ],
        description: "Gebäude E.3 ist ein Laborgebäude des Fachbereichs Bauwesen (B).",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8197b9",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "" }
            ]
        }
    },

    {
        id: "Gebaeude_E_2",
        title: "Gebäude E.2 Bauforum",
        icon: "assets/gebaeude_E_2_bauforum.svg",
        images: [
            "assets/gebaeude_E_2_bauforum_01.jpg",
            "assets/gebaeude_E_2_bauforum_02.jpg",
            "assets/gebaeude_E_2_bauforum_03.jpg",
            "assets/gebaeude_E_2_bauforum_04.jpg",
            "assets/gebaeude_E_2_bauforum_05.jpg"
        ],
        description: "Das Bauforum ist ein Veranstaltungsort mit viel Raum für Begegnung, Exponate und Austausch.<br>Das Gebäude verbindet das Laborgebäude E.3 mit dem Vorlesungsbereich Gebäude E.1 und fungiert als repräsentativer Eingangsbereich für den Fachbereich Bauwesen. Das großzügige Foyer des Bauforums dient als zentrale Kommunikationsfläche und wird regelmäßig für Ausstellungen, Vorträge und Fachveranstaltungen genutzt.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8197b9",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_E_1",
        title: "Gebäude E.1",
        icon: "assets/gebaeude_E_1.svg",
        iconHeight: "130px",
        images: [
            "assets/gebaeude_E_1_01.jpg",
            "assets/gebaeude_E_1_02.jpg"
        ],
        description: "Im Gebäude E.1 befinden sich die Vorlesungsräume sowie das Sekretariat des Fachbereichs Bauwesen (B).<br><br>Ebenfalls ist hier das Labor für Baustoffe, das Labor für Hydrologie und Internationale Wasserwirtschaft und das RoboLab zu finden.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8197b9",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_A_1",
        title: "Gebäude A.1",
        icon: "assets/gebaeude_A_1.svg",
        images: [
            "assets/gebaeude_A_1_06.jpg",
            "assets/gebaeude_A_1_05.jpg",
            "assets/gebaeude_A_1_01.jpg",
            "assets/gebaeude_A_1_02.jpg",
            "assets/gebaeude_A_1_03.jpg",
            "assets/gebaeude_A_1_04.jpg"
        ],
        description: "Im Gebäude A.1 befinden sich die zentralen Verwaltungseinheiten der TH Lübeck. Darunter Personal, Finanzen, Studierendensekretariat, das International Office und das Präsidium mit Besuchersekretariat im 1. Obergeschoss. Außerdem findest du hier die Studienberatung, die Zulassungsstelle, das Sprachenzentrum, die Stabsstelle Forschung und Transfer sowie die Druckerei. <br><br>Ein zentraler Service Point steht ebenfalls als erste Kontaktstelle für allgemeine Anfragen zur Verfügung. Das Serviceangebot umfasst administrative und studienbezogene Anliegen.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#f0847f",
            color: "#212529",
            slots: [
                { label: "Gebäude Mo - Fr:", time: "06:00 - 19:30 Uhr" },
                { label: "Service Point Mo u. Mi:", time: "13:00 - 15:00 Uhr" },
                { label: "Service Point Do:", time: "09:00 - 12:00 Uhr" },
                { label: "Telefon:", time: "+49 451 300 6" },
                { label: "E-Mail:", time: "kontakt(at)th-luebeck.de" }
            ]
        }
    },

    {
        id: "Gebaeude_D_4",
        title: "Gebäude D.4",
        icon: "assets/gebaeude_D_4.svg",
        images: [
            "assets/gebaeude_D_4_01.jpg",
            "assets/gebaeude_D_4_02.jpg",
            "assets/gebaeude_D_4_03.jpg"
        ],
        description: "Gebäude D.4 ist ein zentrales Hörsaalgebäude auf dem Campus und verfügt über Vorlesungssäle sowie studentische Arbeitsplätze, die häufig für Veranstaltungen wie das Lübecker Orientierungssemester (LOS) genutzt werden. <br><br>Außerdem findest du hier die AStA-Cafeteria mit dem AStA-Shop, den IT-Support, die Pressestelle sowie einen Still- und Wickelraum.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#cad391",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_D_3",
        title: "Gebäude D.3",
        icon: "assets/gebaeude_D_3.svg",
        iconHeight: "90px",
        images: [
            "assets/gebaeude_D_3_01.jpg",
            "assets/gebaeude_D_3_02.jpg"
        ],
        description: "Die Seagulls Luebeck sind das Formula Student Team der Technischen Hochschule Lübeck, gegründet 2018. Jährlich entwerfen, fertigen und führen sie einen Rennwagen im internationalen Konstruktionswettbewerb „Formula Student“ vor.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#cad391",
            color: "#212529",
            slots: [
                { label: "Mo, Mi, Do:", time: "10:00 - 22:00 Uhr" },
                { label: "Di und Fr:", time: "10:00 - 23:00 Uhr" },
                { label: "Sa:", time: "geschlossen" },
                { label: "So:", time: "12:00 - 16:00 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_D_2",
        title: "Gebäude D.2",
        icon: "assets/gebaeude_D_2.svg",
        iconHeight: "140px",
        images: [
            "assets/gebaeude_D_2_01.jpg",
            "assets/gebaeude_D_2_02.jpg",
            "assets/gebaeude_D_2_03.jpg"
        ],
        description: "Das Solarhaus dient als Reallabor für energieautarkes Wohnen ohne fossile Energieträger und verfügt über Messplätze für Langzeituntersuchungen von Solarmodulen sowie ein digitales System zur Klima- und Wetterdatenaufzeichnung. <br><br>Im Inneren stehen Labore für Photovoltaik, darunter ein Indoor-Sonnensimulator, sowie ein Thermoelektrik-Labor zur Verfügung. <br><br>Ergänzt wird das Angebot durch praxisnahe Lehr- und Forschungsformate, mit Praktika in Solartechnik, Thermodynamik und Simulation regenerativer Energiesysteme in Studiengängen wie Physikalische Technik, Umweltingenieurwesen und Biomedizintechnik.",
    },


    {
        id: "Gebaeude_D_1",
        title: "Gebäude D.1",
        icon: "assets/gebaeude_D_1.svg",
        iconHeight: "120px",
        images: [
            "assets/gebaeude_D_1_01.jpg",
            "assets/gebaeude_D_1_02.jpg"
        ],
        description: "Der JuniorCampus der TH Lübeck bietet Vorschulkindern einen spielerischen Zugang zu Wissen durch praktisches Experimentieren. <br><br>Ziel ist es, neben naturwissenschaftlichen Grundlagen auch Kreativität, soziale Kompetenzen und Neugier zu fördern. Dabei setzen sich Kinder mit Fragen aus den MINT-Bereichen (Mathematik, Informatik, Naturwissenschaften und Technik) auseinander.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#cad391",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "09:00 - 15:00 Uhr" },
                { label: "Sa:", time: "10:00 - 16:00 Uhr" },
                { label: "So:", time: "geschlossen" }
            ]
        }
    },

    {
        id: "Gebaeude_C_4",
        title: "Gebäude C.4",
        icon: "assets/gebaeude_C_4.svg",
        images: [
            "assets/gebaeude_C_5_01.jpg",
            "assets/gebaeude_C_5_02.jpg",
            "assets/gebaeude_C_5_03.jpg",
            "assets/gebaeude_C_5_04.jpg",
            "assets/gebaeude_C_5_05.jpg",
            "assets/gebaeude_C_5_06.jpg"
        ],
        description: "Das Gebäude C.4 beherbergt viele Seminar- und Vorlesungsräume. Außerdem dient das Atrium der Technischen Hochschule Lübeck als zentrales Foyer und Kommunikationstreffpunkt im Hochschulgebäude. <br><br>Hier ist auch die Cafeteria, die Café-Lounge Bits+Bytes, zu finden. Außerdem sitzt im Gebäude C.4 die Haustechnik.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8fbbdb",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_C_3",
        title: "Gebäude C.3",
        icon: "assets/gebaeude_C_3.svg",
        iconHeight: "100px",
        images: [
            "assets/gebaeude_C_4_02.jpg",
            "assets/gebaeude_C_4_01.jpg",
            "assets/gebaeude_C_4_03.jpg",
            "assets/gebaeude_C_4_04.jpg"
        ],
        description: "Gebäude C.3 ist ein Hörsaal-Gebäude. <br><br>Hier findet man auch das Sekretariat zum Fachbereich Elektrotechnik und Informatik (EI) und das Sekretariat zum Fachbereich Maschinenbau und Wirtschaft (MW).",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8fbbdb",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_C_2b",
        title: "Gebäude C.2b",
        icon: "assets/gebaeude_C_2b.svg",
        iconHeight: "140px",
        images: [
            "assets/gebaeude_C_3_01.jpg",
            "assets/gebaeude_C_3_02.jpg"
        ],
        description: "Im Gebäude C.2b befinden sich Vorlesungsräume.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8fbbdb",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_C_2a",
        title: "Gebäude C.2a",
        icon: "assets/gebaeude_C_2a.svg",
        iconHeight: "140px",
        images: [
            "assets/gebaeude_C_2_01.jpg",
            "assets/gebaeude_C_2_02.jpg"
        ],
        description: "Im Gebäude C.2a befinden sich Vorlesungsräume.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8fbbdb",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_C_1",
        title: "Gebäude C.1",
        icon: "assets/gebaeude_C_1.svg",
        iconHeight: "140px",
        images: [
            "assets/gebaeude_C_1_01.jpg",
            "assets/gebaeude_C_1_02.jpg",
            "assets/gebaeude_C_1_03.jpg",
            "assets/gebaeude_C_1_04.jpg"
        ],
        description: "Gebäude C.1 ist ein Laborgebäude Physikalische Technik des Fachbereichs Angewandte Naturwissenschaften (AN).",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#8fbbdb",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_9",
        title: "Gebäude F.9",
        icon: "assets/gebaeude_F_9.svg",
        iconHeight: "120px",
        images: [
            "assets/gebaeude_F_9_01.jpg",
            "assets/gebaeude_F_9_02.jpg",
            "assets/gebaeude_F_9_03.jpg",
            "assets/gebaeude_F_9_04.jpg",
            "assets/gebaeude_F_9_05.jpg"
        ],
        description: "Gebäude F.9 ist ein Laborgebäude für die Fachbereiche Angewandte Naturwissenschaften, Elektrotechnik und Informatik und Maschinenbau und Wirtschaft.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#96b98d",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_8",
        title: "Gebäude F.8",
        icon: "assets/gebaeude_F_8.svg",
        iconHeight: "100px",
        images: [
            "assets/gebaeude_F_8_01.jpg"
        ],
        description: "Gebäude F.8 ist ein Hochspannungslabor / EMV (Elektromagnetischen Verträglichkeit)  mit Verteilerstation.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#96b98d",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_7",
        title: "Gebäude F.7",
        icon: "assets/gebaeude_F_7.svg",
        iconHeight: "120px",
        images: [
            "assets/gebaeude_F_7_01.jpg"
        ],
        description: "Im Gebäude F.7 befindet sich die Marktüberwachung Schleswig-Holstein.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#96b98d",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_6",
        title: "Gebäude F.6",
        icon: "assets/gebaeude_F_6.svg",
        iconHeight: "120px",
        images: [
            "assets/gebaeude_F_6_01.jpg",
            "assets/gebaeude_F_6_02.jpg",
            "assets/gebaeude_F_6_03.jpg",
            "assets/gebaeude_F_6_04.jpg"
        ],
        description: "Gebäude F.6 ist eine Materialprüfanstalt (MPA).",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#96b98d",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_5",
        title: "Gebäude F.5",
        icon: "assets/gebaeude_F_5.svg",
        images: [
            "assets/gebaeude_F_5_01.jpg",
            "assets/gebaeude_F_5_02.jpg",
            "assets/gebaeude_F_5_03.jpg",
            "assets/gebaeude_F_5_04.jpg"
        ],
        description: "Gebäude F.5, häufig als „E-Technik“ bezeichnet, befindet sich auf dem Hochschulgelände und ist die zentrale Anlaufstelle für praktisches Lernen im Maschinenbau. Es wird insbesondere für Werkstatt- und Werkstoffprüfungen genutzt, etwa im Rahmen des Maschinenbau-Studiums, wo Studierende dort technische Bauteile herstellen und testen können. <br><br>Teilweise finden dort auch Escape-Room-Aktivitäten zur Studienorientierung statt.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#96b98d",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_4",
        title: "Gebäude F.4",
        icon: "assets/gebaeude_F_4.svg",
        images: [
            "assets/gebaeude_F_4_01.jpg",
            "assets/gebaeude_F_4_02.jpg",
            "assets/gebaeude_F_4_03.jpg",
            "assets/gebaeude_F_4_04.jpg"
        ],
        description: "Gebäude F.4 ist eine Maschinenhalle / Werkstatt.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#96b98d",
            color: "#212529",
            slots: [
                { label: "Mo - Fr:", time: "06:00 - 19:30 Uhr" }
            ]
        }
    },

    {
        id: "Gebaeude_F_3",
        title: "Gebäude F.3",
        icon: "assets/gebaeude_F_3.svg",
        iconHeight: "100px",
        images: [
            "assets/gebaeude_F_3_01.jpg",
            "assets/gebaeude_F_3_02.jpg",
        ],
        description: "Gebäude F.3 ist ein Kesselhaus / Strömungslehre.",
    },

    {
        id: "Gebaeude_F_2",
        title: "Gebäude F.2",
        icon: "assets/gebaeude_F_2.svg",
        iconHeight: "100px",
        images: [
            "assets/gebaeude_F_2_01.jpg"
        ],
        description: "Gebäude F.2 ist die Hausmeisterwohnung.",
    },

    {
        id: "Gebaeude_F_1",
        title: "Gebäude F.1",
        icon: "assets/gebaeude_F_1.svg",
        iconHeight: "100px",
        images: [
            "assets/gebaeude_F_1_01.jpg"
        ],
        description: "Gebäude F.1 ist ein Lager.",
    },

    {
        id: "Kaffee_Campus_Taste",
        title: "Campus Taste",
        icon: "assets/campus_taste.svg",
        iconHeight: "110px",
        images: [
            "assets/campus_taste_02.jpg",
            "assets/campus_taste_01.jpg",
            "assets/campus_taste_03.jpg",
            "assets/campus_taste_04.jpg",
            "assets/campus_taste_05.jpg"
        ],
        description: "Das Campus Taste im MFC 1 bietet frische Säfte, Snacks, Burger- und Nudelangebote, sowie Kaffeespezialitäten an.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#f39325",
            color: "##343a40",
            slots: [
                { label: "Mo - Fr:", time: "08:00 - 18:00 Uhr" }
            ]
        }
    },

    {
        id: "Kaffee_Cafeteria",
        title: "Cafeteria",
        icon: "assets/cafeteria.svg",
        iconHeight: "90px",
        images: [
            "assets/cafeteria_01.jpg"
        ],
        description: "Die Cafeteria im Mensagebäude bietet ein vielseitiges Angebot an frisch belegten Baguettes und Brötchen, Snacks wie Currywurst oder Gebäck, sowie heiße und kalte Getränke. Hier ist auch Barzahlung möglich.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#f39325",
            color: "##343a40",
            slots: [
                { label: "Mo - Fr:", time: "09:30 - 14:30 Uhr" }
            ]
        }
    },

    {
        id: "Kaffee_Kiosk",
        title: "Kiosk",
        icon: "assets/kiosk.svg",
        iconHeight: "90px",
        images: [
            "assets/kiosk_04.jpg",
            "assets/kiosk_02.jpg",
            "assets/kiosk_01.jpg",
            "assets/kiosk_03.jpg"
        ],
        description: "Der Kiosk an der Stephensonstraße bietet Studierenden, Mitarbeitenden und Besucher*innen auf dem Campus eine zentrale Anlaufstelle für Snacks, Getränke sowie Press­eartikel.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#f39325",
            color: "##343a40",
            slots: [
                { label: "Mo - Do:", time: "7:45 - 16:30" },
                { label: "Fr:", time: "7:45 - 14:30" }
            ]
        }
    },

    {
        id: "Kaffee_Bits_Bytes",
        title: "Bits+Bytes",
        icon: "assets/bits_bytes.svg",
        iconHeight: "90px",
        images: [
            "assets/bit_bytes_01.jpg",
            "assets/bit_bytes_02.jpg",
            "assets/bit_bytes_03.jpg",
            "assets/bit_bytes_04.jpg"
        ],
        description: "Die Café-Lounge „Bits + Bytes“ bietet auf 200 Sitzplätzen eine Kombination aus Lern- und Aufenthaltsort. Angeboten werden vielfältige warme Snacks, frische Waffeln, Kaffeespezialitäten und Desserts.",
        openingHours: {
            label: "Öffnungszeiten",
            bgColor: "#f39325",
            color: "##343a40",
            slots: [
                { label: "Mo - Fr:", time: "9:30 - 14:30" }
            ]
        }
    },

    {
        id: "Fahrradstation_Gebaeude_C_4",
        title: "Fahrradstation Gebäude C.4",
        icon: "assets/fahrradstation.svg",
        iconHeight: "90px",
        images: [
            "assets/fahrradstation_gebaeude_C_4.jpg"
        ],
        description: "Direkt am Hauptzugang von Gebäude C.4 befindet sich eine öffentliche Fahrradreparaturstation. Diese Station ermöglicht kleinere Selbstreparaturen. Zur Ausstattung gehören diverse Werkzeuge wie Konusschlüssel, Zange, Sechskantschlüssel sowie eine Pumpe mit Manometer, um den Reifendruck einfach zu prüfen und anzupassen.",
    },

    {
        id: "Fahrradstation_Gebaeude_G_1",
        title: "Fahrradstation Gebäude G.1",
        icon: "assets/fahrradstation.svg",
        iconHeight: "90px",
        images: [
            "assets/fahrradstation_gebaeude_G_1.jpg"
        ],
        description: "Neben Gebäude G.1, etwa in Richtung Gefahrstofflager befindet sich eine öffentliche Fahrradreparaturstation. Diese Station ermöglicht kleinere Selbstreparaturen. Zur Ausstattung gehören diverse Werkzeuge wie Konusschlüssel, Zange, Sechskantschlüssel sowie eine Pumpe mit Manometer, um den Reifendruck einfach zu prüfen und anzupassen.",
    },
    {
        id: "Fahrradstation_Wohnheim",
        title: "Fahrradstation am Wohnheim",
        icon: "assets/fahrradstation.svg",
        iconHeight: "90px",
        images: [
            "assets/fahrradstation_am_wohnheim.jpg"
        ],
        description: "Am Wohnheim befindet sich eine öffentliche Fahrradreparaturstation. Diese Station ermöglicht kleinere Selbstreparaturen. Zur Ausstattung gehören diverse Werkzeuge wie Konusschlüssel, Zange, Sechskantschlüssel sowie eine Pumpe mit Manometer, um den Reifendruck einfach zu prüfen und anzupassen.",
    },
    {
        id: "Fahrradstation_Studentendorf",
        title: "Fahrradstation am Studentendorf",
        icon: "assets/fahrradstation.svg",
        iconHeight: "90px",
        images: [
            "assets/fahrradstation_am_studentendorf.jpg"
        ],
        description: "Am Studentendorf befindet sich eine öffentliche Fahrradreparaturstation. Diese Station ermöglicht kleinere Selbstreparaturen, mit Tools wie Konusschlüssel, Zange, Sechskantschlüssel und einer Pumpe mit Manometer.",
    },

    {
        id: "Fahrradstation_Audimax",
        title: "Fahrradstation am Audimax",
        icon: "assets/fahrradstation.svg",
        iconHeight: "90px",
        images: [
            "assets/fahrradstation_am_audimax.jpg"
        ],
        description: "Neben dem Audimax befindet sich eine öffentliche Fahrradreparaturstation. Diese Station ermöglicht kleinere Selbstreparaturen, mit Tools wie Konusschlüssel, Zange, Sechskantschlüssel und einer Pumpe mit Manometer.",
    },




    { // Bushaltestellen
        id: "Bus_Stephensonstraße",
        title: "Bushaltestelle Stephensonstraße",
        iconHeight: "90px",
        images: [
            "assets/bushaltestelle_stephensonstrasse.jpg"
        ],
        description: "Hier halten folgende Linien",
        openingHours: {
            label: "Linie",
            bgColor: "#ffe71f",
            color: "##343a40",
            slots: [
                { label: "8 Richtung Bornkamp", time: "" },
                { label: "8 Richtung ZOB/Hauptbahnhof", time: "" },
                { label: "9 nur zum Anhalten", time: "" },
                { label: "30 Richtung Gneversdorf", time: "" }
            ]
        },
        link: {
            url: "https://www.swhl.de/mobil/fahrplanauskunft/haltestellen/stephensonstrasse/",
            text: "Haltestellenaushänge einsehen"
        }
    },

    { // Bushaltestellen
        id: "Bus_Bessemer_Straße_Sereetz",
        title: "Bushaltestelle Bessemer Straße",
        iconHeight: "90px",
        images: [
            "assets/bus_bessemer_strasse_sereetz.jpg"
        ],
        description: "Hier halten folgende Linien",
        openingHours: {
            label: "Linie",
            bgColor: "#ffe71f",
            color: "##343a40",
            slots: [
                { label: "1 Richtung Sereetz", time: "" },
                { label: "8 Richtung ZOB/Hauptbahnhof", time: "" },
                { label: "30 Richtung Stephensonstraße", time: "" }
            ]
        },
        link: {
            url: "https://www.swhl.de/mobil/fahrplanauskunft/haltestellen/bessemer-strasse/",
            text: "Haltestellenaushänge einsehen"
        }
    },

    { // Bushaltestellen
        id: "Bus_Bessemer_Straße_Bornkamp",
        title: "Bushaltestelle Bessemer Straße",
        iconHeight: "90px",
        images: [
            "assets/bus_bessemer_strasse_bornkamp.jpg"
        ],
        description: "Hier halten folgende Linien",
        openingHours: {
            label: "Linie",
            bgColor: "#ffe71f",
            color: "##343a40",
            slots: [
                { label: "1 Richtung Hochschulstadtteil", time: "" },
                { label: "8 Richtung Bornkamp", time: "" },
                { label: "30 Richtung Gneversdorf", time: "" }
            ]
        },
        link: {
            url: "https://www.swhl.de/mobil/fahrplanauskunft/haltestellen/bessemer-strasse/",
            text: "Haltestellenaushänge einsehen"
        }
    },

    { // Bushaltestellen
        id: "Bus_Technische_Hochschule_Sereetz",
        title: "Bushaltestelle Technische Hochschule",
        iconHeight: "90px",
        images: [
            "assets/bus_technische_hochschule_sereetz.jpg"
        ],
        description: "Hier halten folgende Linien",
        openingHours: {
            label: "Linie",
            bgColor: "#ffe71f",
            color: "##343a40",
            slots: [
                { label: "1 Richtung Sereetz", time: "" },
                { label: "9 Richtung Bad Schwartau", time: "" }
            ]
        },
        link: {
            url: "https://www.swhl.de/mobil/fahrplanauskunft/haltestellen/technische-hochschule/",
            text: "Haltestellenaushänge einsehen"
        }
    },

    { // Bushaltestellen
        id: "Bus_Technische_Hochschule_Grillenweg",
        title: "Bushaltestelle Technische Hochschule",
        iconHeight: "90px",
        images: [
            "assets/bus_technische_hochschule_grillenweg.jpg"
        ],
        description: "Hier halten folgende Linien",
        openingHours: {
            label: "Linie",
            bgColor: "#ffe71f",
            color: "##343a40",
            slots: [
                { label: "1 Richtung Hochschulstadtteil", time: "" },
                { label: "9 Richtung Grillenweg", time: "" }
            ]
        },
        link: {
            url: "https://www.swhl.de/mobil/fahrplanauskunft/haltestellen/technische-hochschule/",
            text: "Haltestellenaushänge einsehen"
        }
    },
];

const filters = [
    { label: 'Quiz', icon: 'assets/quiz_icon_einstellungen_an.svg', id: ['Studierende_mit_Fragen'], defaultVisible: true },
    { label: 'Fahrradstation', icon: 'assets/fahrrad_icon_einstellungen_an.svg', id: ['Fahrradstationen', 'Fahrradstation Audimax', 'Fahrradstation Studentendorf'], defaultVisible: true },
    { label: 'Bushaltestelle', icon: 'assets/bus_icon_einstellungen_an.svg', id: ['Bushaltestellen'], defaultVisible: true },
    { label: 'Kiosk & Café', icon: 'assets/kaffee_icon_einstellungen_an.svg', id: ['Kaffee'], defaultVisible: true },
    { label: 'Buttons', icon: 'assets/butten_icon_einstellungen_an.svg', id: ['Buttons'], defaultVisible: true },
    // Ebenen aus dem offiziellen Campusplan (nur in der Karte nach dem Intro vorhanden)
    { label: 'Info & Sammelplatz', icon: 'assets/info_icon_einstellungen_an.svg', id: ['Infopunkte'], defaultVisible: true },
    { label: 'WC', icon: 'assets/wc_icon_einstellungen_an.svg', id: ['WC'], defaultVisible: true },
    { label: 'Barrierefreiheit', icon: 'assets/barrierefreiheit_icon_einstellungen_an.svg', id: ['Barrierefreiheit', 'Aufzuege'], defaultVisible: false },
    { label: 'Schranken & Zufahrt', icon: 'assets/schranke_icon_einstellungen_an.svg', id: ['Zufahrt'], defaultVisible: true },
];

const CLICKABLE_Geb_CONFIG = {
    lottieMap: {
        prefixMatches: [],
        exactMatches: [
            "MFC_8", "MFC_7", "MFC_1", "GruenderCube_2",
            "GruenderCube_1", "Gebaeude_E_5", "Gebaeude_E_3",
            "Gebaeude_E_2", "Gebaeude_E_1", "Gebaeude_E_4",
            "Gebaeude_D_4", "Gebaeude_D_3", "Gebaeude_D_1",
            "Gebaeude_D_2", "Gebaeude_F_3", "Gebaeude_F_4",
            "Gebaeude_F_2", "Gebaeude_F_1", "Gebaeude_F_7",
            "Gebaeude_F_6", "Gebaeude_F_8", "Gebaeude_F_9",
            "Gebaeude_F_5", "_Uebergang_bei_Gebaeude_C_5_und_C_4",
            "_Uebergang_bei_Gebaeude_C_4_und_C_3", "_Uebergang_bei_Gebaeude_C_3_und_C_2",
            "_Uebergang_bei_Gebaeude_C_2_und_C_1", "Gebaeude_C_5",
            "Gebaeude_C_4", "Gebaeude_C_3", "Gebaeude_C_2",
            "Gebaeude_C_1", "Gebaeude_C_2b", "Gebaeude_C_2a",
            "Audimax_B_65", "Bibliothek_B_60", "Mensa_B_59",
            "Gebaeude_B_64",
            "Gebaeude_A_1", "Gebaeude_G_3", "_Uebergang_bei_Gebaeude_G_3_und_G_2",
            "Gebaeude_G_2", "_Uebergang_bei_Gebaeude_G_2_und_G_1", "Gebaeude_G_1", "Frage", "Frage-2", "Frage-3", "Frage-4", "Frage-5", "Frage-6", "Frage-7", "Frage-8", "Frage-9", "Frage-10", "Button_FabLab", "Button_Speiseplan", "Button_Erkundungstour", "Button_Innenstadt", "Button_Studium", "Button_Hochschulsport", "Kaffee_Campus_Taste", "Kaffee_Cafeteria", "Kaffee_Kiosk", "Kaffee_Bits_Bytes", "Logo", "Fahrradstation_Wohnheim", "Fahrradstation_Studentendorf", "Fahrradstation_Gebaeude_C_4","Fahrradstation_Gebaeude_G_1", "Fahrradstation_Audimax", "Bus_Stephensonstraße", "Bus_Technische_Hochschule_Grillenweg", "Bus_Technische_Hochschule_Sereetz", "Bus_Bessemer_Straße_Sereetz", "Bus_Bessemer_Straße_Bornkamp"
        ],
        excludeMatches: [
        ]
    }
};

const ALL_BADGES = [
    {
        id: 'stay_curious',
        url: 'assets/badge_stay_curious.svg',
        name: 'Stay Curious',
        description: 'Schließe dein erstes Quiz ab',
        milestone: 1
    },
    {
        id: 'challenge_accepted',
        url: 'assets/badge_challenge_accepted.svg',
        name: 'Challenge Accepted',
        description: 'Schließe 5 Quizze ab',
        milestone: 5
    },
    {
        id: 'campus_expert',
        url: 'assets/badge_campus_expert.svg',
        name: 'Campus Expert',
        description: 'Schließe alle 10 Quizze ab',
        milestone: 10
    }
];
