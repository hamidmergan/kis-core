# Embedding the campus map

The campus map can be embedded on other pages too, as a stand-alone iframe.

```html
<iframe
    src="https://kis.th-luebeck.de/campus-map/?lang=en"
    title="Campus map TH Lübeck"
    width="100%"
    height="700"
    style="border:0; display:block; max-width:100%;"
    loading="lazy"
    allowfullscreen
    allow="clipboard-write"
    referrerpolicy="no-referrer-when-downgrade">
</iframe>
```

## Straight to a building

Appended to the address, `?show=B.59` jumps straight to that building, `&lang=de` switches the map to German.
