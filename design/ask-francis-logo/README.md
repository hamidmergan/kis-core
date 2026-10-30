# ASK Francis logo

Name in Geist as outlines, ASK in weight 800 and the header blue #004261, Francis in weight 500, no bird.

- `ask-francis-logo-white-plate.svg` white plate, not transparent, for coloured grounds such as the blue header
- `ask-francis-logo-transparent-black.svg` transparent, ASK blue and Francis black, for light grounds
- `ask-francis-logo-transparent-white.svg` transparent, both words white, for dark grounds, only the weight sets ASK apart
- PNG at 256, 512, 1024 and 2048 px width, transparent

Regenerate: `pip install fonttools brotli uharfbuzz`, then `python build_logo.py` and `NODE_PATH=../../frontend/node_modules node render_png.js`.
