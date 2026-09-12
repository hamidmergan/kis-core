import { ROLES, type Language, type Line, type Person, type Role } from "./_types";

interface SampleLine {
  role: Role;
  text: string;
}

export const DEFAULT_NAMES = ["Lena", "Jonas", "Amira", "Tom"] as const;

const DIALOG: Record<Language, SampleLine[]> = {
  de: [
    { role: "host", text: "Willkommen zum Podcast. Heute geht es um das Ohmsche Gesetz, und mit dabei ist {expert}. Schön, dass du da bist." },
    { role: "expert", text: "Danke, {host}. Das Ohmsche Gesetz ist das Erste, was man in der Elektrotechnik lernt, und ehrlich gesagt kommt man nie wieder davon los." },
    { role: "host", text: "Dann fangen wir ganz vorne an. Was sagt das Gesetz eigentlich?" },
    { role: "expert", text: "Es verbindet drei Größen. Die Spannung U, den Strom I und den Widerstand R. Die Formel lautet U gleich R mal I. Wenn ich zwei davon kenne, kann ich die dritte ausrechnen." },
    { role: "student", text: "Darf ich kurz nachfragen? Warum heißt es Gesetz, wenn es doch nur eine Formel ist?" },
    { role: "expert", text: "Gute Frage. Es beschreibt, wie sich reale Bauteile verhalten. Bei einem Metallwiderstand steigt der Strom genau proportional zur Spannung. Das ist eine Beobachtung, keine Definition." },
    { role: "critic", text: "Aber das gilt eben nicht immer. Eine Diode oder eine Glühlampe halten sich nicht daran. Da wird gern so getan, als wäre das universell." },
    { role: "expert", text: "Stimmt, und das ist wichtig. Das Gesetz gilt für ohmsche Widerstände. Bei einer Glühlampe ändert sich der Widerstand mit der Temperatur, deshalb ist die Kennlinie gekrümmt." },
    { role: "host", text: "Machen wir es konkret. Hast du ein Beispiel aus dem Labor?" },
    { role: "expert", text: "Nimm einen Widerstand von 100 Ohm an 5 Volt. Dann fließen 50 Milliampere. Verdoppelst du die Spannung auf 10 Volt, fließen 100 Milliampere. Genau linear." },
    { role: "student", text: "Und wenn ich den Widerstand nicht kenne, messe ich einfach Spannung und Strom und teile?" },
    { role: "expert", text: "Genau so. Das ist im Praktikum die erste Messung überhaupt. Multimeter dran, zwei Werte ablesen, teilen, fertig." },
    { role: "critic", text: "Wobei das Multimeter selbst einen Innenwiderstand hat. Bei kleinen Strömen verfälscht das die Messung spürbar." },
    { role: "host", text: "Das klingt nach einem Thema für die nächste Folge. Was sollten sich alle merken?" },
    { role: "expert", text: "U gleich R mal I. Und die Frage, ob das Bauteil überhaupt ohmsch ist, bevor man rechnet." },
    { role: "host", text: "Danke {expert}, und danke euch fürs Zuhören. Bis zum nächsten Mal." },
  ],
  en: [
    { role: "host", text: "Welcome to the podcast. Today we talk about Ohm's law, and with me is {expert}. Great to have you here." },
    { role: "expert", text: "Thanks, {host}. Ohm's law is the first thing you learn in electrical engineering, and honestly you never get away from it." },
    { role: "host", text: "Then let's start from the very beginning. What does the law actually say?" },
    { role: "expert", text: "It connects three quantities. The voltage U, the current I and the resistance R. The formula is U equals R times I. If I know two of them, I can work out the third." },
    { role: "student", text: "Can I ask something quickly? Why is it called a law if it is just a formula?" },
    { role: "expert", text: "Good question. It describes how real components behave. With a metal resistor the current rises exactly in proportion to the voltage. That is an observation, not a definition." },
    { role: "critic", text: "But that does not always hold. A diode or a light bulb does not follow it. People like to pretend it is universal." },
    { role: "expert", text: "True, and that matters. The law holds for ohmic resistors. In a light bulb the resistance changes with temperature, so the characteristic curve bends." },
    { role: "host", text: "Let's make it concrete. Do you have an example from the lab?" },
    { role: "expert", text: "Take a resistor of 100 ohms at 5 volts. Then 50 milliamps flow. Double the voltage to 10 volts and 100 milliamps flow. Exactly linear." },
    { role: "student", text: "And if I do not know the resistance, I just measure voltage and current and divide?" },
    { role: "expert", text: "Exactly. That is the very first measurement in the lab course. Multimeter on, read two values, divide, done." },
    { role: "critic", text: "Although the multimeter has an internal resistance of its own. With small currents that noticeably distorts the measurement." },
    { role: "host", text: "That sounds like a topic for the next episode. What should everyone remember?" },
    { role: "expert", text: "U equals R times I. And the question whether the component is ohmic at all, before you calculate." },
    { role: "host", text: "Thank you {expert}, and thanks to all of you for listening. See you next time." },
  ],
};

const MONOLOG: Record<Language, string[]> = {
  de: [
    "Heute geht es um das Ohmsche Gesetz, die erste Formel der Elektrotechnik und eine, die dich durchs ganze Studium begleitet.",
    "Es verbindet drei Größen. Die Spannung U, den Strom I und den Widerstand R. U gleich R mal I.",
    "Kennst du zwei davon, rechnest du die dritte aus. Ein Widerstand von 100 Ohm an 5 Volt lässt 50 Milliampere fließen.",
    "Verdoppelst du die Spannung, verdoppelt sich der Strom. Das ist die Proportionalität, um die es geht.",
    "Wichtig ist die Einschränkung. Das Gesetz gilt für ohmsche Widerstände, also für Bauteile mit gerader Kennlinie.",
    "Eine Glühlampe hält sich nicht daran, weil ihr Widerstand mit der Temperatur steigt. Eine Diode erst recht nicht.",
    "Im Praktikum ist das die erste Messung. Spannung und Strom ablesen, teilen, und du hast den Widerstand.",
    "Merk dir also zwei Dinge. Die Formel, und die Frage, ob das Bauteil überhaupt ohmsch ist.",
  ],
  en: [
    "Today we look at Ohm's law, the first formula in electrical engineering and one that stays with you for the whole degree.",
    "It connects three quantities. The voltage U, the current I and the resistance R. U equals R times I.",
    "Know two of them and you work out the third. A resistor of 100 ohms at 5 volts lets 50 milliamps flow.",
    "Double the voltage and the current doubles. That is the proportionality this is all about.",
    "The restriction matters. The law holds for ohmic resistors, that is components with a straight characteristic curve.",
    "A light bulb does not follow it, because its resistance rises with temperature. A diode even less.",
    "In the lab course this is the first measurement. Read voltage and current, divide, and you have the resistance.",
    "So remember two things. The formula, and the question whether the component is ohmic at all.",
  ],
};

let seq = 0;
const newId = () => `l${Date.now().toString(36)}${(seq++).toString(36)}`;

/** The stand-in for the model: a fixed script, spread over the people by their roles. */
export function sampleScript(language: Language, persons: Person[]): Line[] {
  const speakerFor = (role: Role) => persons.findIndex((p) => p.role === role);
  const names = Object.fromEntries(
    ROLES.map((role, i) => [role, persons[speakerFor(role)]?.name ?? persons[i % persons.length].name]),
  ) as Record<Role, string>;
  const fill = (text: string) => text.replace(/\{(host|expert|student|critic)\}/g, (_, role: Role) => names[role]);
  if (persons.length === 1) {
    return MONOLOG[language].map((text) => ({ id: newId(), speaker: 0, text: fill(text), audioOf: null }));
  }
  return DIALOG[language]
    .filter((l) => speakerFor(l.role) >= 0)
    .map((l) => ({ id: newId(), speaker: speakerFor(l.role), text: fill(l.text), audioOf: null }));
}
