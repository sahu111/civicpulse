// Make the built Tailwind CSS work in older browsers (Chrome 109 / Firefox 115, the last
// versions on Windows 7): converts oklch() colours to rgb and adds other fallbacks.
const fs = require("fs");
const { transform } = require("lightningcss");

const file = "static/css/app.css";
const v = (major) => major << 16;
const { code } = transform({
  filename: file,
  code: fs.readFileSync(file),
  minify: true,
  targets: { chrome: v(109), firefox: v(115), edge: v(109), safari: v(15) },
});
fs.writeFileSync(file, code);
console.log("legacy-css: done", code.length, "bytes");
