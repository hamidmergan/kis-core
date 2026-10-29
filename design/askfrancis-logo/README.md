# askFrancis logo

Name in Geist SemiBold as outlines, bird from `frontend/public/logos/kis-vogel.svg`, ask in the bird's green, Francis in black.

- `askfrancis-logo-white-plate.svg` white plate, not transparent, for coloured grounds such as the blue header
- `askfrancis-logo-transparent-black.svg` transparent, Francis black, for light grounds
- `askfrancis-logo-transparent-white.svg` transparent, Francis white, for dark grounds
- PNG at 256, 512, 1024 and 2048 px width, transparent

Regenerate: `pip install fonttools brotli uharfbuzz`, then `python build_logo.py` and `NODE_PATH=../../frontend/node_modules node render_png.js`.
