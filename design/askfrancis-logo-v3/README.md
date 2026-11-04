# askFrancis logo

Name in Geist as outlines, "ask" in weight 800 and the corporate blue #004261, "Francis" in weight 500.

- `askfrancis-logo-plate.svg` white round plate, Francis in a blue circle, for coloured grounds
- `askfrancis-logo-transparent-black.svg` transparent, blue circle with Francis, for light grounds
- `askfrancis-logo-transparent-white.svg` transparent, both words white, Francis free on the left, for the blue header and dark grounds
- the same three with `-ohne-francis`: name only
- PNG at 256, 512, 1024 and 2048 px width, transparent
- `francis-idle.svg` is Francis rendered from `frontend/src/components/ui/Francis.tsx`, state idle, no shadow

Regenerate: `pip install fonttools brotli uharfbuzz`, then `python build_logo.py` and `NODE_PATH=../../frontend/node_modules node render_png.js`.
