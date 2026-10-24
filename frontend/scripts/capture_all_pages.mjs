/**
 * scripts/capture_all_pages.mjs
 * Playwright script to capture screenshots across all 6 pages at 1440px, 1024px, and 390px
 * in both Dark and Light themes.
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const outputDir = path.resolve('public/screenshots');
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const PAGES = [
  { name: 'today', route: '/' },
  { name: 'coach', route: '/coach' },
  { name: 'nutrition', route: '/nutrition' },
  { name: 'workouts', route: '/workouts' },
  { name: 'tracker', route: '/tracker' },
  { name: 'profile', route: '/profile' },
  { name: 'design', route: '/design' },
];

const VIEWPORTS = [
  { name: '1440px_desktop', width: 1440, height: 900 },
  { name: '1024px_tablet', width: 1024, height: 800 },
  { name: '390px_mobile', width: 390, height: 844 },
];

const THEMES = ['dark', 'light'];

async function run() {
  console.log('Starting Playwright screenshot capture...');
  const browser = await chromium.launch({ headless: true });

  for (const pageItem of PAGES) {
    for (const theme of THEMES) {
      for (const vp of VIEWPORTS) {
        const context = await browser.newContext({
          viewport: { width: vp.width, height: vp.height },
        });
        const page = await context.newPage();

        await page.addInitScript((t) => {
          window.localStorage.setItem('fitbot_theme', t);
        }, theme);

        try {
          await page.goto(`http://localhost:5173${pageItem.route}`, {
            waitUntil: 'networkidle',
            timeout: 15000,
          });

          await page.evaluate((t) => {
            if (t === 'dark') {
              document.documentElement.classList.add('dark');
              document.documentElement.classList.remove('light');
            } else {
              document.documentElement.classList.add('light');
              document.documentElement.classList.remove('dark');
            }
          }, theme);

          await page.waitForTimeout(800);

          const filename = `${pageItem.name}_${vp.name}_${theme}.png`;
          const filepath = path.join(outputDir, filename);
          await page.screenshot({ path: filepath, fullPage: false });
          console.log(`[OK] Captured: ${filename}`);
        } catch (err) {
          console.error(`[ERR] ${pageItem.name} ${vp.name} ${theme}:`, err.message);
        } finally {
          await context.close();
        }
      }
    }
  }

  await browser.close();
  console.log('All screenshots captured successfully in public/screenshots/');
}

run();
