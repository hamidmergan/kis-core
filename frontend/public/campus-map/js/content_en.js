// Englische Inhalte – werden bei Sprache "en" ueber config_v2.js gelegt.
//
// Enthaelt nur die Textfelder, in derselben Struktur wie config_v2.js.
// Arrays werden elementweise (per Index) zusammengefuehrt: Reihenfolge und
// Laenge muessen also zum deutschen Original passen. Wer in config_v2.js
// Texte aendert oder Eintraege ergaenzt, sollte sie hier nachziehen –
// fehlende Eintraege erscheinen einfach auf Deutsch.

const CONTENT_EN_QUIZ = {
    Frage: {
        content: {
            question: 'Which learning platform does TH Lübeck use?',
            options: [
                { text: 'Stud.IP' },
                { text: 'Lernraum' },
                { text: 'Student portal' },
                { text: 'Moodle' }
            ]
        },
        campusInfo: {
            text: 'TH Lübeck organizes the semester on “Lernraum”, a platform based on Moodle. There you can sign up for your courses and find all the information and materials throughout the semester.',
            link: { text: 'More about Lernraum at TH Lübeck' }
        }
    },
    Frage2: {
        description: 'Memory – find the sports offered at TH Lübeck',
        content: {
            pairs: [
                { label: 'Dragon boat' },
                { label: 'Judo' },
                { label: 'K-Pop' },
                { label: 'Aerial silks' },
                { label: 'Underwater rugby' },
                { label: 'Volleyball' }
            ]
        },
        campusInfo: {
            text: 'Into sports and staying active alongside your studies? University sports offer you plenty of ways to stay fit and try out new sports.',
            link: { text: 'Go to Hochschulsport Lübeck (university sports)' }
        }
    },
    Frage3: {
        content: {
            question: 'What is the THL logo supposed to represent?',
            options: [
                { text: 'The Holsten Gate' },
                { text: 'The Eye of Sauron' },
                { text: 'An abstract identifying mark' },
                { text: 'The sun over the Baltic Sea' }
            ],
            successMessage: 'Correct! The logo isn\'t a concrete symbol but an abstract identifying mark.'
        },
        campusInfo: {
            text: 'The logo isn\'t a concrete symbol but an abstract identifying mark of the Technische Hochschule Lübeck.',
            link: { text: 'Visit the TH Lübeck website' }
        }
    },
    Frage4: {
        content: {
            question: 'Put the steps of applying to study at THL in the right order:',
            items: [
                'I register on the THL application portal',
                'I enter my personal details',
                'I state which degree program I want to apply for',
                'I upload my university entrance qualification to the online portal',
                'I submit my application in the online portal'
            ]
        },
        campusInfo: {
            text: 'Interested in studying at the Technische Hochschule Lübeck? Then you simply apply online through our application portal. You can find all the steps here:',
            link: { text: 'Step-by-step guide from TH Lübeck' }
        }
    },
    Frage5: {
        content: {
            question: 'Find all the terms about student life at TH Lübeck:',
            words: [
                { display: 'Dorm', search: 'DORM' },
                { display: 'AStA', search: 'ASTA' },
                { display: 'Klokurier', search: 'KLOKURIER' },
                { display: 'COAL Festival', search: 'COAL' },
                { display: 'Erasmus', search: 'ERASMUS' },
                { display: 'TH Choir', search: 'CHOIR' },
                { display: 'Stressbar', search: 'STRESSBAR' },
                { display: 'University Gaming', search: 'GAMING' },
                { display: 'BAföG', search: 'BAFOEG' },
                { display: 'Scholarships', search: 'SCHOLARSHIPS' }
            ]
        },
        campusInfo: {
            accordionItems: [
                { title: 'Dorm', text: 'You can find info about student dorms in Lübeck at the', link: { text: 'Studentenwerk Schleswig-Holstein' } },
                { title: 'AStA', text: 'The General Students\' Committee represents your interests and organizes lots of events. More info:', link: { text: 'AStA TH Lübeck' } },
                { title: 'Klokurier', text: 'The student newspaper of TH Lübeck:', link: { text: 'Klokurier website' } },
                { title: 'COAL Festival', text: 'Campus Open Air Lübeck – the biggest festival of Lübeck\'s universities:', link: { text: 'COAL Festival' } },
                { title: 'Erasmus', text: 'Study abroad with Erasmus+: find out more at the', link: { text: 'International Office TH Lübeck' } },
                { title: 'TH Choir', text: 'The Lübeck university choir offers a musical community and performances. Info:', link: { text: 'University choir' } },
                { title: 'Stressbar', text: 'The legendary student bar “Stress” on the Lübeck campus. More info:', link: { text: 'Stress Bar' } },
                { title: 'University Gaming Lübeck', text: 'The gaming community at TH Lübeck organizes tournaments and meetups. More info:', link: { text: 'Hochschulgaming Lübeck' } },
                { title: 'BAföG', text: 'Info on financing your studies with BAföG (German federal student aid) from', link: { text: 'TH Lübeck' } },
                { title: 'Scholarships', text: 'Various scholarships such as the Deutschlandstipendium or subject-specific funding:', link: { text: 'Info on scholarships' } }
            ]
        }
    },
    Frage6: {
        content: {
            question: 'Which two degree programs are NOT offered at TH Lübeck?',
            options: [
                { label: 'Civil Engineering' },
                { label: 'Game Design' },
                { label: 'Hearing Acoustics' },
                { label: 'Computer Science' },
                { label: 'Biomedical Engineering' },
                { label: 'IT Security' },
                { label: 'Mechanical Engineering' },
                { label: 'International Management' },
                { label: 'Architecture' }
            ]
        },
        campusInfo: {
            text: 'The Technische Hochschule Lübeck offers a wide range of degree programs in engineering, natural sciences, construction and business. There are bachelor\'s and master\'s degrees, many of them also available online or as dual study programs.',
            link: { text: 'All degree programs at a glance – TH Lübeck' }
        }
    },
    Frage7: {
        content: {
            question: 'What can you do to get a better idea of whether studying at THL is right for you?',
            options: [
                { text: 'Shadow students with the Studienlotsen (student guides) on a university day' },
                { text: 'Book an appointment with the (subject-specific) study advisory service' },
                { text: 'Take part in a trial study program or an orientation semester' },
                { text: 'Contact the student council of the degree program you\'re interested in' }
            ]
        },
        campusInfo: {
            items: [
                { text: 'Deciding to go to university can be a big challenge. That\'s why we want to support you as best we can along the way. You can find info on personal advice here:', link: { text: 'Personal advice | Technische Hochschule Lübeck' } },
                { text: 'and offers for school students and prospective students here:', link: { text: 'Orientation offers for school students and prospective students' } }
            ]
        }
    },
    Frage8: {
        content: {
            question: 'What\'s missing for a safe lab experiment? Click on all the safety issues.',
            imageAlt: 'Picture puzzle: students working at a lab bench with pipettes, samples and a centrifuge.',
            hotspots: [
                { label: 'Eating in the lab' },
                { label: 'Spilled sample' },
                { label: 'No safety goggles' },
                { label: 'No safety goggles (2nd person)' },
                { label: 'No lab coat' }
            ]
        },
        campusInfo: {
            text: 'At TH, hands-on practice is a big deal. You don\'t just gain knowledge here – you also get to apply it right away in various lab courses and practicals.'
        }
    },
    Frage9: {
        content: {
            question: 'What time does the Central University Library (ZHB) usually open?',
            options: [
                { text: '9:00 a.m.' },
                { text: '8:00 a.m.' },
                { text: '11:30 a.m.' },
                { text: '7:15 a.m.' }
            ]
        },
        campusInfo: {
            text: 'The ZHB is a great place to study or do research. Besides lots of books, there are several individual and group work tables as well as rooms you can book. And if you don\'t feel like going to the library, you can access plenty of books online from home via interlibrary loan.',
            link: { text: 'More information about the ZHB' }
        }
    },
    Frage10: {
        content: {
            question: 'Which study terms are we looking for?',
            words: [
                { answer: 'CAFETERIA', clue: 'Where students eat lunch' },
                { answer: 'PROFESSOR', clue: 'University teacher' },
                { answer: 'LECTURE', clue: 'Type of class where a teacher presents to many students' },
                { answer: 'AUDITORIUM', clue: 'Room where lectures take place' },
                { answer: 'EXAM', clue: 'Test at the end of the semester' },
                { answer: 'BACHELOR', clue: 'First academic degree' },
                { answer: 'CAMPUS', clue: 'University grounds' },
                { answer: 'BAFOEG', clue: 'German state financial aid for students' },
                { answer: 'SEMESTER', clue: 'Half of an academic year' },
                { answer: 'AUDIMAX', clue: 'Largest lecture hall on campus' }
            ]
        },
        campusInfo: {
            text: 'If the puzzle made you curious, you\'ll find more tips and offers for prospective students on the website of the Technische Hochschule Lübeck.',
            link: { text: 'Study orientation at TH Lübeck' }
        }
    }
};
const CONTENT_EN_FILTERS = [
    { label: 'Quiz' },
    { label: 'Bike station' },
    { label: 'Bus stop' },
    { label: 'Kiosk & café' },
    { label: 'Buttons' },
    { label: 'Info & assembly point' },
    { label: 'Toilets' },
    { label: 'Accessibility' },
    { label: 'Barriers & access' }
];
const CONTENT_EN_BADGES = {
    stay_curious: { description: 'Complete your first quiz' },
    challenge_accepted: { description: 'Complete 5 quizzes' },
    campus_expert: { description: 'Complete all 10 quizzes' }
};

const CONTENT_EN_BUILDINGS = {
    Mensa_B_59: {
        title: 'Mensa (Dining Hall) B.59',
        description: 'The Mensa (dining hall) is on campus next to the library and the Audimax and serves three to four fresh dishes every day, including at least one vegetarian option. Alongside the daily changing menu, you\'ll also find a selection of desserts. <br><br>For kids, there are high chairs, a play corner and a baby changing table.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '11:15 – 14:15' },
                { label: 'Zero-waste plate:', time: '14:15 – 14:30' },
                { label: 'Semester break:', time: '11:15 – 13:30' }
            ]
        }
    },
    Audimax_B_65: {
        title: 'Audimax B.65',
        description: 'The Audimax is the central lecture hall complex on the campus shared by TH Lübeck and the University of Lübeck. Its lecture hall AM 1 is a large auditorium with extensive media technology and special facilities for music events. <br>Two more halls, AM 2 and AM 3, offer modern equipment for lectures and seminars. <br><br>The Audimax is regularly used for events such as talks, career days and festival programs.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Bibliothek_B_60: {
        title: 'Library B.60',
        description: 'The Central University Library Lübeck (ZHB) is a joint academic institution of TH Lübeck and the University of Lübeck. It provides members of both universities with up-to-date literature in medicine, engineering, computer science, natural sciences, business and civil engineering. <br><br>Inside you\'ll find a PC pool, a quiet study room, special study rooms for blind and visually impaired users, group study rooms and a student lounge with 20 seats.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '09:00 – 22:30 (loans at the circulation desk: 09:00 – 18:00)' },
                { label: 'Sat:', time: '09:00 – 20:00 (circulation desk: 09:00 – 13:00)' },
                { label: 'Sun:', time: '10:00 – 20:00 (loans via self-service machine only)' }
            ]
        }
    },
    Gebaeude_B_64: {
        title: 'Building B.64',
        description: 'Building B.64 houses the Biomedical Engineering laboratory building (AN) and the TANDEM competence center (Technology and Engineering in Medicine). <br><br>It is also home to numerous institutes of the University of Lübeck, such as the Institute of Computer Engineering, the Institute for Neuro- and Bioinformatics, the Institute of Information Systems, the Institute for IT Security, the IT Service Center and IMIS (Institute for Multimedia and Interactive Systems).'
    },
    MFC_7: {
        title: 'MFC 7',
        description: 'MFC VII (Multifunctional Center 7) at Maria-Goeppert-Straße 9 is home to, among others, TH Lübeck\'s Institute for Interactive Systems (ISy), which carries out pioneering research in digital education, learning analytics, AI and human-centered design and runs numerous externally funded projects. <br><br> MFC VII also houses the Center for Digital Teaching (ZDL), which supports lecturers in digitally enhanced university teaching.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 18:00' }
            ]
        }
    },
    MFC_8: {
        title: 'MFC 8',
        description: 'MFC VIII (Multifunctional Center 8) at Maria-Goeppert-Straße 9a is home to FabLab Lübeck, an open high-tech workshop for prototyping with 3D printers, laser cutters and CNC machines.<br><br>The building also houses the Institute of Psychology I (IPSY I) of the University of Lübeck.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 18:00' }
            ]
        }
    },
    MFC_1: {
        title: 'MFC 1',
        description: 'MFC I (Multifunctional Center 1) at Maria-Goeppert-Straße 1 is an office building not far from Carlebach Park. <br><br>Among other things, it houses the Technikzentrum Lübeck (TZL, technology center) and Campus Taste.',
        openingHours: {
            label: 'Office hours of the Technikzentrum Lübeck (TZL)',
            slots: [
                { label: 'Mon – Fri:', time: '08:00 – 16:00' }
            ]
        }
    },
    Gebaeude_G_1: {
        title: 'Building G.1',
        description: 'Building G.1 is a laboratory building of the Department of Applied Natural Sciences (AN). It also houses the AN department office and the Center for Industrial Biotechnology (CIB).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_G_2: {
        title: 'Building G.2',
        description: 'Building G.2 is a laboratory building of the Departments of Applied Natural Sciences (AN) and Mechanical Engineering and Business (MW). There\'s also a nursing and baby changing room here.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_G_3: {
        title: 'Building G.3',
        description: 'Building G.3 is a laboratory building of the Department of Electrical Engineering and Computer Science (EI). <br>On the second floor you\'ll find the CoSA competence center (Communication – Systems – Applications) of the Department of Electrical Engineering and Computer Science.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    GruenderCube_1: {
        title: 'GründerCube 1',
        description: 'GründerCube 1 is a joint start-up advisory center of TH Lübeck and the University of Lübeck. <br><br>It supports students, researchers and alumni all the way from finding an idea to founding a start-up, with advice, workshops, events and a broad network.'
    },
    GruenderCube_2: {
        title: 'GründerCube 2',
        description: 'GründerCube 2 expands the start-up center. <br><br>The flexibly designed module adds almost 98 m² of extra space to the first Cube, including advisory rooms and workspaces – ideal for individual project work and start-up advice in a quiet setting.'
    },
    Gebaeude_E_5: {
        title: 'Building E.5',
        description: 'Building E.5 houses parts of the university administration as well as the office of the company doctor. The building has no step-free access and no elevator.'
    },
    Gebaeude_E_4: {
        title: 'Building E.4',
        description: 'Building E.4 houses the student councils for Applied Natural Sciences (FS AN), Civil Engineering (FS BAU) and Technology and Business (FS TW), which support students in all student matters. <br><br>The building is also home to the Student Parliament (StuPa) and the AStA (General Students\' Committee).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Tue & Thu:', time: '13:15 – 14:00' }
            ]
        }
    },
    Gebaeude_E_3: {
        title: 'Building E.3',
        description: 'Building E.3 is a laboratory building of the Department of Civil Engineering (B).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '' }
            ]
        }
    },
    Gebaeude_E_2: {
        title: 'Building E.2 Bauforum',
        description: 'The Bauforum is an event venue with plenty of space for encounters, exhibits and exchange.<br>The building connects laboratory building E.3 with lecture building E.1 and serves as the representative entrance to the Department of Civil Engineering. Its spacious foyer is a central meeting space and is regularly used for exhibitions, talks and specialist events.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_E_1: {
        title: 'Building E.1',
        description: 'Building E.1 houses the lecture rooms and the office of the Department of Civil Engineering (B).<br><br>You\'ll also find the Building Materials Laboratory, the Laboratory for Hydrology and International Water Management, and the RoboLab here.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_A_1: {
        title: 'Building A.1',
        description: 'Building A.1 houses TH Lübeck\'s central administration, including Human Resources, Finance, the Student Registry (Studierendensekretariat), the International Office and the Presidential Office with its visitor reception on the first floor. You\'ll also find Student Advisory Services, the Admissions Office, the Language Center, the Research and Transfer Office and the print shop here. <br><br>A central Service Point is your first point of contact for general inquiries and helps with administrative and study-related matters.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Building Mon – Fri:', time: '06:00 – 19:30' },
                { label: 'Service Point Mon & Wed:', time: '13:00 – 15:00' },
                { label: 'Service Point Thu:', time: '09:00 – 12:00' },
                { label: 'Phone:', time: '+49 451 300 6' },
                { label: 'Email:', time: 'kontakt(at)th-luebeck.de' }
            ]
        }
    },
    Gebaeude_D_4: {
        title: 'Building D.4',
        description: 'Building D.4 is a central lecture hall building on campus with lecture halls and student workspaces, which are often used for events such as the Lübeck Orientation Semester (LOS). <br><br>You\'ll also find the AStA cafeteria with the AStA shop, IT Support, the Press Office and a nursing and baby changing room here.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_D_3: {
        title: 'Building D.3',
        description: 'The Seagulls Luebeck are TH Lübeck\'s Formula Student team, founded in 2018. Every year they design and build a race car and present it at the international engineering design competition “Formula Student”.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon, Wed, Thu:', time: '10:00 – 22:00' },
                { label: 'Tue & Fri:', time: '10:00 – 23:00' },
                { label: 'Sat:', time: 'closed' },
                { label: 'Sun:', time: '12:00 – 16:00' }
            ]
        }
    },
    Gebaeude_D_2: {
        title: 'Building D.2',
        description: 'The Solarhaus (solar house) serves as a real-world laboratory for energy-self-sufficient living without fossil fuels. It has measuring stations for long-term testing of solar modules and a digital system for recording climate and weather data. <br><br>Inside, there are photovoltaics labs, including an indoor solar simulator, as well as a thermoelectrics lab. <br><br>This is complemented by hands-on teaching and research formats, with lab courses in solar technology, thermodynamics and the simulation of renewable energy systems in degree programs such as Physical Engineering, Environmental Engineering and Biomedical Engineering.'
    },
    Gebaeude_D_1: {
        title: 'Building D.1',
        description: 'TH Lübeck\'s JuniorCampus gives preschool children a playful approach to knowledge through hands-on experiments. <br><br>Besides basic science, the aim is to foster creativity, social skills and curiosity. The children explore questions from the STEM fields (mathematics, computer science, natural sciences and technology).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '09:00 – 15:00' },
                { label: 'Sat:', time: '10:00 – 16:00' },
                { label: 'Sun:', time: 'closed' }
            ]
        }
    },
    Gebaeude_C_4: {
        title: 'Building C.4',
        description: 'Building C.4 houses many seminar rooms and lecture halls. Its atrium serves as TH Lübeck\'s central foyer and meeting point. <br><br>This is also where you\'ll find the cafeteria, the Bits+Bytes café lounge. Building C.4 is also home to Facility Management (Haustechnik).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_C_3: {
        title: 'Building C.3',
        description: 'Building C.3 is a lecture hall building. <br><br>Here you\'ll also find the offices of the Department of Electrical Engineering and Computer Science (EI) and the Department of Mechanical Engineering and Business (MW).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_C_2b: {
        title: 'Building C.2b',
        description: 'Building C.2b houses lecture rooms.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_C_2a: {
        title: 'Building C.2a',
        description: 'Building C.2a houses lecture rooms.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_C_1: {
        title: 'Building C.1',
        description: 'Building C.1 is the Physical Engineering laboratory building of the Department of Applied Natural Sciences (AN).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_9: {
        title: 'Building F.9',
        description: 'Building F.9 is a laboratory building for the Departments of Applied Natural Sciences, Electrical Engineering and Computer Science, and Mechanical Engineering and Business.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_8: {
        title: 'Building F.8',
        description: 'Building F.8 is a high-voltage / EMC (electromagnetic compatibility) laboratory with a distribution substation.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_7: {
        title: 'Building F.7',
        description: 'Building F.7 houses the Schleswig-Holstein market surveillance authority (Marktüberwachung).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_6: {
        title: 'Building F.6',
        description: 'Building F.6 is a materials testing institute (MPA).',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_5: {
        title: 'Building F.5',
        description: 'Building F.5, often called “E-Technik”, is located on the university grounds and is the central hub for hands-on learning in mechanical engineering. It is used in particular for workshop practice and materials testing, for example in the Mechanical Engineering degree program, where students can manufacture and test technical components. <br><br>It sometimes also hosts escape room activities for study orientation.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_4: {
        title: 'Building F.4',
        description: 'Building F.4 is a machine hall / workshop.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '06:00 – 19:30' }
            ]
        }
    },
    Gebaeude_F_3: {
        title: 'Building F.3',
        description: 'Building F.3 is a boiler house / fluid mechanics lab.'
    },
    Gebaeude_F_2: {
        title: 'Building F.2',
        description: 'Building F.2 is the caretaker\'s apartment.'
    },
    Gebaeude_F_1: {
        title: 'Building F.1',
        description: 'Building F.1 is a storage building.'
    },
    Kaffee_Campus_Taste: {
        title: 'Campus Taste',
        description: 'Campus Taste in MFC 1 offers fresh juices, snacks, burgers and pasta dishes, as well as specialty coffees.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '08:00 – 18:00' }
            ]
        }
    },
    Kaffee_Cafeteria: {
        title: 'Cafeteria',
        description: 'The cafeteria in the Mensa building offers a wide range of freshly filled baguettes and rolls, snacks such as currywurst or pastries, and hot and cold drinks. You can also pay in cash here.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '09:30 – 14:30' }
            ]
        }
    },
    Kaffee_Kiosk: {
        title: 'Kiosk',
        description: 'The kiosk on Stephensonstraße is a central spot on campus for students, staff and visitors to grab snacks, drinks, newspapers and magazines.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Thu:', time: '07:45 – 16:30' },
                { label: 'Fri:', time: '07:45 – 14:30' }
            ]
        }
    },
    Kaffee_Bits_Bytes: {
        title: 'Bits+Bytes',
        description: 'With 200 seats, the “Bits + Bytes” café lounge is both a place to study and a place to hang out. It offers a variety of hot snacks, fresh waffles, specialty coffees and desserts.',
        openingHours: {
            label: 'Opening hours',
            slots: [
                { label: 'Mon – Fri:', time: '09:30 – 14:30' }
            ]
        }
    },
    Fahrradstation_Gebaeude_C_4: {
        title: 'Bike Repair Station at Building C.4',
        description: 'Right by the main entrance of Building C.4 there is a public bike repair station where you can do minor repairs yourself. It is equipped with various tools such as cone wrenches, pliers and hex keys, plus a pump with a pressure gauge so you can easily check and adjust your tire pressure.'
    },
    Fahrradstation_Gebaeude_G_1: {
        title: 'Bike Repair Station at Building G.1',
        description: 'Next to Building G.1, roughly towards the hazardous materials store, there is a public bike repair station where you can do minor repairs yourself. It is equipped with various tools such as cone wrenches, pliers and hex keys, plus a pump with a pressure gauge so you can easily check and adjust your tire pressure.'
    },
    Fahrradstation_Wohnheim: {
        title: 'Bike Repair Station at the Residence Hall',
        description: 'At the residence hall there is a public bike repair station where you can do minor repairs yourself. It is equipped with various tools such as cone wrenches, pliers and hex keys, plus a pump with a pressure gauge so you can easily check and adjust your tire pressure.'
    },
    Fahrradstation_Studentendorf: {
        title: 'Bike Repair Station at the Studentendorf',
        description: 'At the Studentendorf (student village) there is a public bike repair station where you can do minor repairs yourself, with tools such as cone wrenches, pliers, hex keys and a pump with a pressure gauge.'
    },
    Fahrradstation_Audimax: {
        title: 'Bike Repair Station at the Audimax',
        description: 'Next to the Audimax there is a public bike repair station where you can do minor repairs yourself, with tools such as cone wrenches, pliers, hex keys and a pump with a pressure gauge.'
    },
    'Bus_Stephensonstraße': {
        title: 'Bus stop Stephensonstraße',
        description: 'The following lines stop here',
        openingHours: {
            label: 'Line',
            slots: [
                { label: '8 towards Bornkamp', time: '' },
                { label: '8 towards ZOB/Hauptbahnhof (main station)', time: '' },
                { label: '9 (drop-off only)', time: '' },
                { label: '30 towards Gneversdorf', time: '' }
            ]
        },
        link: {
            text: 'View timetables for this stop'
        }
    },
    'Bus_Bessemer_Straße_Sereetz': {
        title: 'Bus stop Bessemer Straße',
        description: 'The following lines stop here',
        openingHours: {
            label: 'Line',
            slots: [
                { label: '1 towards Sereetz', time: '' },
                { label: '8 towards ZOB/Hauptbahnhof (main station)', time: '' },
                { label: '30 towards Stephensonstraße', time: '' }
            ]
        },
        link: {
            text: 'View timetables for this stop'
        }
    },
    'Bus_Bessemer_Straße_Bornkamp': {
        title: 'Bus stop Bessemer Straße',
        description: 'The following lines stop here',
        openingHours: {
            label: 'Line',
            slots: [
                { label: '1 towards Hochschulstadtteil', time: '' },
                { label: '8 towards Bornkamp', time: '' },
                { label: '30 towards Gneversdorf', time: '' }
            ]
        },
        link: {
            text: 'View timetables for this stop'
        }
    },
    Bus_Technische_Hochschule_Sereetz: {
        title: 'Bus stop Technische Hochschule',
        description: 'The following lines stop here',
        openingHours: {
            label: 'Line',
            slots: [
                { label: '1 towards Sereetz', time: '' },
                { label: '9 towards Bad Schwartau', time: '' }
            ]
        },
        link: {
            text: 'View timetables for this stop'
        }
    },
    Bus_Technische_Hochschule_Grillenweg: {
        title: 'Bus stop Technische Hochschule',
        description: 'The following lines stop here',
        openingHours: {
            label: 'Line',
            slots: [
                { label: '1 towards Hochschulstadtteil', time: '' },
                { label: '9 towards Grillenweg', time: '' }
            ]
        },
        link: {
            text: 'View timetables for this stop'
        }
    }
};

applyContentOverlay('en', {
    quizModals: CONTENT_EN_QUIZ,
    campusBuildings: CONTENT_EN_BUILDINGS,
    filters: CONTENT_EN_FILTERS,
    badges: CONTENT_EN_BADGES
});
