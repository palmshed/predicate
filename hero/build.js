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

function buildLogoPath() {
  return `
    <circle cx="${PADDING_X + 30}" cy="${PADDING_Y + 30}" r="32" fill="#24d455" fill-opacity="0.12"/>
    <path d="M${PADDING_X + 22} ${PADDING_Y + 18}c0-4.4-6.2-8-14-8s-14 3.6-14 8h4l2-2 2 2h8" stroke="#24d455" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M${PADDING_X + 22} ${PADDING_Y + 16.3}A14.6 14.6 0 0 1 ${PADDING_X + 28} ${PADDING_Y + 14}c7.6 0 14 5.6 14 14h-6l-2-2-2 2h-6" stroke="#24d455" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M${PADDING_X + 2.7} ${PADDING_Y + 21.8}c-5.4 5.4-5.8 13.7-.9 18.6l10.6-10.6 1.8-1.8 1.8-1.8 5.3-5.3c-4.9-4.9-13.2-4.5-18.6.9" stroke="#24d455" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M${PADDING_X + 15} ${PADDING_Y + 33.8}c1.2 6.3-.4 11.3-2.5 16.3h10c5-13.8-1.3-30-2.5-35" stroke="#24d455" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
}

function build() {
  const svg = `<svg width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="${WIDTH}" height="${HEIGHT}" fill="#0D1117"/>
  ${buildLogoPath()}
  <text x="${PADDING_X + 80}" y="${PADDING_Y + 22}" font-family="Inter, -apple-system, BlinkMacSystemFont, sans-serif" font-size="36" font-weight="600" fill="#FFFFFF">Predicate</text>
  <text x="${PADDING_X + 80}" y="${PADDING_Y + 48}" font-family="Inter, -apple-system, BlinkMacSystemFont, sans-serif" font-size="16" fill="#8B949E">Natural Language to SQL Engine</text>
  ${buildBadges()}
</svg>`;

  const outPath = path.resolve(__dirname, "../.github/website/hero.svg");
  fs.writeFileSync(outPath, svg.trim() + "\n");
  console.log(`Generated: ${outPath}`);
}

build();
