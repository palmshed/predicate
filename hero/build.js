const fs = require("fs");
const path = require("path");
const { badges } = require("./badges");

const WIDTH = 900;
const HEIGHT = 200;
const PADDING_X = 60;
const PADDING_Y = 50;

function buildBadge(badge, xOffset) {
  const padding = 12;
  const measuredWidth = badge.label.length * 7 + padding * 2;
  const height = 24;
  const rx = 12;
  const fillOpacity = 0.12;

  return `
    <rect x="${xOffset}" y="${PADDING_Y + 92}" width="${measuredWidth}" height="${height}" rx="${rx}" fill="${badge.color}" fill-opacity="${fillOpacity}"/>
    <text x="${xOffset + measuredWidth / 2}" y="${PADDING_Y + 108}" font-family="Inter, -apple-system, BlinkMacSystemFont, sans-serif" font-size="11" font-weight="500" fill="${badge.color}" text-anchor="middle">${badge.label}</text>`;
}

function buildBadges() {
  let x = PADDING_X;
  return badges.map((badge) => {
    const svg = buildBadge(badge, x);
    const padding = 12;
    x += badge.label.length * 7 + padding * 2 + 10;
    return svg;
  }).join("");
}

function buildLogo() {
  const logoX = PADDING_X;
  const logoY = PADDING_Y - 5;
  const logoSize = 70;

  return `
  <g transform="translate(${logoX}, ${logoY}) scale(${logoSize / 24})">
    <circle cx="12" cy="12" r="12" fill="#24d455" fill-opacity="0.12"/>
    <path d="M13 8c0-2.76-2.46-5-5.5-5S2 5.24 2 8h2l1-1 1 1h4" stroke="#24d455" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M13 7.14A5.82 5.82 0 0 1 16.5 6c3.04 0 5.5 2.24 5.5 5h-3l-1-1-1 1h-3" stroke="#24d455" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M5.89 9.71c-2.15 2.15-2.3 5.47-.35 7.43l4.24-4.25.7-.7.71-.71 2.12-2.12c-1.95-1.96-5.27-1.8-7.42.35" stroke="#24d455" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M11 15.5c.5 2.5-.17 4.5-1 6.5h4c2-5.5-.5-12-1-14" stroke="#24d455" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </g>`;
}

function build() {
  const textX = PADDING_X + 80;

  const svg = `<svg width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="${WIDTH}" height="${HEIGHT}" fill="#0D1117"/>
  ${buildLogo()}
  <text x="${textX}" y="${PADDING_Y + 22}" font-family="Inter, -apple-system, BlinkMacSystemFont, sans-serif" font-size="36" font-weight="600" fill="#FFFFFF">Predicate</text>
  <text x="${textX}" y="${PADDING_Y + 48}" font-family="Inter, -apple-system, BlinkMacSystemFont, sans-serif" font-size="16" fill="#8B949E">Natural Language to SQL Engine</text>
  ${buildBadges()}
</svg>`;

  const outPath = path.resolve(__dirname, "../.github/website/hero.svg");
  fs.writeFileSync(outPath, svg.trim() + "\n");
  console.log(`Generated: ${outPath}`);
}

build();
