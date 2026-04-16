import Header from "@/components/layout/Header";

export default function ImpressumPage() {
  return (
    <>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold mb-6">Impressum</h1>

          <p className="font-semibold text-gray-700 mb-2">
            Angaben gemäß § 5 DDG:
          </p>
          <p className="text-gray-600 mb-4">
            Hamid Mergan<br />
            Mönkhofer Weg 239<br />
            23562 Lübeck
          </p>

          <p className="font-semibold text-gray-700 mb-2">Kontakt:</p>
          <p className="text-gray-600">
            Telefon: +49 451 160818 81<br />
            E-Mail: hamid.mergan@th-luebeck.de
          </p>
        </div>
      </div>
    </>
  );
}
