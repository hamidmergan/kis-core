// Renders each ASK Francis logo SVG to transparent PNGs at several widths through headless Chromium.
const { chromium } = require("@playwright/test");
const fs = require("fs");
const OUT = __dirname;
const NAMES = ["ask-francis-logo-white-plate", "ask-francis-logo-transparent-black", "ask-francis-logo-transparent-white"];
const WIDTHS = [256, 512, 1024, 2048];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: 2200, height: 600 } });
  for (const name of NAMES) {
    const data = fs.readFileSync(`${OUT}/${name}.svg`).toString("base64");
    for (const w of WIDTHS) {
      await page.setContent(`<body style="margin:0;background:transparent"><img id="i" src="data:image/svg+xml;base64,${data}" style="width:${w}px;display:block"></body>`);
      await page.waitForFunction(() => document.getElementById("i").complete);
      await page.locator("#i").screenshot({ path: `${OUT}/${name}-${w}.png`, omitBackground: true });
    }
    console.log(name, "png ok");
  }
  await browser.close();
})();
