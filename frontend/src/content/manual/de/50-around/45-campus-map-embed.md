# Campusplan einbinden

Der Campusplan lässt sich auch auf anderen Seiten einbinden, als eigenständiges iframe.

```html
<iframe
    src="https://kis.th-luebeck.de/campus-map/?lang=de"
    title="Campusplan TH Lübeck"
    width="100%"
    height="700"
    style="border:0; display:block; max-width:100%;"
    loading="lazy"
    allowfullscreen
    allow="clipboard-write"
    referrerpolicy="no-referrer-when-downgrade">
</iframe>
```

## Direkt auf ein Gebäude

An die Adresse angehängt springt `?show=B.59` gleich zu diesem Gebäude, `&lang=en` stellt die Karte auf Englisch.
