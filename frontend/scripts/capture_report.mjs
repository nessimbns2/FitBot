/** Capture real FitBot screens for the technical report, using a disposable demo account. */
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(root, 'report', 'images');
const base = process.env.FITBOT_BASE_URL || 'http://localhost:5173';
const password = `Report-${crypto.randomBytes(12).toString('hex')}`;
const manifest = { captured_at: new Date().toISOString(), base_url: base, synthetic_demo_data: true, screenshots: [], api_checks: [] };
let bearer = '';

async function api(url, method = 'GET', data) {
  const start = performance.now();
  const res = await fetch(`${base}${url}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}) },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  manifest.api_checks.push({ path: url, method, status: res.status, elapsed_ms: Math.round(performance.now() - start) });
  if (!res.ok) throw new Error(`${method} ${url}: ${res.status} ${(await res.text()).slice(0, 180)}`);
  return res.status === 204 ? null : res.json();
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1.5 });
const page = await context.newPage();
page.setDefaultTimeout(45000);
page.on('pageerror', e => console.error('PAGE ERROR:', e.message));
await context.addInitScript(() => localStorage.setItem('fitbot_theme', 'light'));
await fs.mkdir(output, { recursive: true });

async function shot(name, title, locator = null) {
  await page.waitForTimeout(450);
  const file = `${name}.png`;
  await (locator || page).screenshot({ path: path.join(output, file), animations: 'disabled' });
  manifest.screenshots.push({ file, title, route: new URL(page.url()).pathname });
  console.log(`CAPTURE ${file}`);
}
async function go(route) {
  await page.goto(`${base}${route}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
}
async function closeDialog() {
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  if (await page.getByRole('dialog').count()) {
    const close = page.getByRole('button', { name: /Close (dialog|drawer)/i }).first();
    if (await close.count()) await close.click();
  }
}
async function action(name, work) {
  try { await work(); } catch (error) {
    console.error(`FAILED ${name}: ${error.message}`);
    manifest.screenshots.push({ feature: name, error: error.message });
    await page.screenshot({ path: path.join(root, '.git', `report-error-${name}.png`) }).catch(() => {});
    await go('/');
  }
}

try {
  await go('/login');
  await shot('01-login', 'Connexion sécurisée');
  await go('/register');
  await page.getByPlaceholder('e.g. Sara Ben Ali').fill('Athlete Démo');
  await page.getByPlaceholder('you@example.com').fill('athlete@example.com');
  await shot('02-register', 'Inscription et validation du mot de passe');

  const registered = await api('/api/auth/register', 'POST', {
    full_name: 'Athlete Démo', email: `report_${crypto.randomBytes(5).toString('hex')}@example.com`, password,
  });
  bearer = registered.access_token;
  await api('/api/user/profile', 'PUT', {
    age: 24, sex: 'male', height_cm: 178, weight_kg: 76, body_fat_pct: 16,
    experience_level: 'intermediate', goal: 'hypertrophy', somatotype: 'mesomorph', activity_level: 'moderate',
  });
  const now = new Date();
  const sets = [];
  for (let week = 0; week < 4; week++) {
    const performed_at = new Date(now.getTime() - (21 - 7 * week) * 86400000).toISOString();
    for (const [i, reps] of [[8, 8, 8], [8, 8, 7], [8, 7, 6], [8, 7, 5]][week].entries()) {
      sets.push({ exercise_id: 'barbell-bench-press', weight: 80, reps, rpe: [7, 7.8, 8.6, 9.4][week], unit: 'kg', set_number: i + 1, performed_at });
    }
    for (const exercise_id of ['barbell-back-squat', 'barbell-bent-over-row']) {
      for (let i = 1; i <= 3; i++) sets.push({ exercise_id, weight: 60 + week * 2.5, reps: 8, rpe: 8, unit: 'kg', set_number: i, performed_at });
    }
  }
  await api('/api/overload/log-set', 'POST', sets);
  for (const meal of [
    { name: 'Flocons d’avoine, yaourt et banane', meal_slot: 'breakfast', calories: 480, protein_g: 30, carbs_g: 65, fat_g: 11 },
    { name: 'Poulet, riz et légumes', meal_slot: 'lunch', calories: 620, protein_g: 45, carbs_g: 72, fat_g: 17 },
  ]) await api('/api/nutrition/log', 'POST', meal);
  const routine = await api('/api/exercises/generate-routine', 'POST', { split: 'upper_lower', days_per_week: 4 });
  await api('/api/exercises/routine', 'PUT', { split: 'upper_lower', days_per_week: 4, routine });
  await context.addInitScript(token => localStorage.setItem('fitbot_access_token', token), bearer);

  await go('/');
  await shot('03-dashboard', 'Tableau de bord personnalisé');

  await action('coach', async () => {
    await go('/coach');
    await page.getByPlaceholder(/Ask anything or log sets/).fill('Réponds en français en 80 mots : quelle est ma cible quotidienne de protéines ? Cite les guides et les chiffres calculés.');
    const stream = page.waitForResponse(r => r.url().includes('/api/chat/stream') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Send message' }).click();
    await stream;
    await page.getByRole('button', { name: 'Stop generation' }).waitFor({ state: 'hidden', timeout: 45000 });
    await shot('04-coach-rag', 'Coach RAG et réponse générée en streaming');
    await page.getByRole('button', { name: /Sources \(/ }).first().click();
    await shot('05-coach-sources', 'Sources documentaires, pages et scores de pertinence');
  });

  await go('/profile');
  await shot('06-profile', 'Profil biométrique et objectifs');
  await action('blueprint', async () => {
    await page.getByRole('button', { name: 'View Your Fitness Blueprint' }).click();
    await page.getByRole('dialog').getByText(/Strengths|Recovery|Nutrition|calories/i).first().waitFor({ timeout: 45000 }).catch(() => {});
    await page.waitForTimeout(3000);
    await shot('07-blueprint', 'Bilan Athlete Blueprint personnalisé', page.getByRole('dialog'));
    await closeDialog();
  });
  await action('somatotype', async () => {
    await go('/profile');
    await page.getByRole('button', { name: 'Not sure? Take AI Quiz' }).click();
    const questions = await api('/api/user/somatotype-questions');
    await shot('08-somatotype-quiz', 'Questionnaire morphologique à cinq questions', page.getByRole('dialog'));
    for (let i = 0; i < questions.length; i++) {
      await page.getByRole('dialog').getByText(questions[i].options[1].label, { exact: true }).click();
      await page.getByRole('button', { name: i === questions.length - 1 ? 'Predict My Somatotype with AI' : 'Next', exact: true }).click();
    }
    await page.getByText('Predicted Primary Somatotype').waitFor();
    await shot('09-somatotype-result', 'Résultat du questionnaire et synthèse IA', page.getByRole('dialog'));
    await closeDialog();
  });
  await action('account', async () => {
    await go('/profile');
    await page.getByRole('heading', { name: 'Account & Security' }).scrollIntoViewIfNeeded();
    await shot('10-account-security', 'Gestion du compte et de la sécurité');
  });

  await go('/nutrition');
  await shot('11-nutrition-targets', 'Calculs nutritionnels et distribution des repas');
  await action('diary', async () => {
    await page.getByRole('heading', { name: 'Today’s Food Diary' }).scrollIntoViewIfNeeded();
    await shot('12-food-diary', 'Journal alimentaire et comparaison aux objectifs');
    await page.getByRole('button', { name: 'Add Meal', exact: true }).click();
    await page.getByPlaceholder('e.g. Chicken and rice').fill('Collation après entraînement');
    await shot('13-food-entry', 'Formulaire de saisie et validation du repas', page.getByRole('dialog'));
    await closeDialog();
  });
  await action('meal-suggestions', async () => {
    await page.getByRole('button', { name: 'Suggest', exact: true }).click();
    await page.getByPlaceholder('e.g. vegetarian, no dairy, quick to cook').fill('Repas simples, sans fruits de mer. Réponds en français.');
    const response = page.waitForResponse(r => r.url().includes('/api/nutrition/suggest-meal') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Get suggestions', exact: true }).click();
    const result = await response;
    await result.finished();
    if (result.status() !== 200) throw new Error('Meal suggestions API returned ' + result.status());
    await page.getByRole('button', { name: 'Review & add' }).first().waitFor();
    await page.getByRole('button', { name: 'Review & add' }).first().scrollIntoViewIfNeeded();
    await shot('14-meal-suggestions', 'Suggestions IA adaptées au budget nutritionnel restant');
  });
  await action('vision-scanner', async () => {
    await go('/nutrition');
    await page.getByRole('button', { name: 'Scan Meal (AI)', exact: true }).click();
    await shot('15-vision-upload', 'Scanner de repas : import de la photographie', page.getByRole('dialog'));
    const photo = path.join(output, 'demo-meal.jpg');
    await page.locator('input[type=file]').setInputFiles(photo);
    const response = page.waitForResponse(r => r.url().includes('/api/nutrition/scan-meal') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Analyze Meal & Extract Macros', exact: true }).click();
    const scanned = await response;
    if (scanned.status() !== 200) throw new Error('Vision API returned ' + scanned.status());
    await page.getByText('Identified Plate Components', { exact: true }).waitFor();
    await shot('15b-vision-result', 'Résultat réel Gemini Vision sur la photo de démonstration', page.getByRole('dialog'));
    manifest.photo_credit = {
      author: 'Anna Pelzer', source: 'https://unsplash.com/photos/bowl-of-vegetable-salads-IGfIGP5ONV0',
      license: 'Unsplash License', local_file: 'demo-meal.jpg',
    };
    await closeDialog();
  });

  await go('/workouts');
  await shot('16-workout-planner', 'Planification de routine et matrice du volume');
  await action('routine-coach', async () => {
    await page.getByRole('button', { name: 'AI Suggest Exercise', exact: true }).click();
    await page.getByRole('dialog', { name: 'AI Routine Coach Analysis' }).waitFor();
    await shot('17-routine-ai', 'Analyse IA du volume et proposition d’exercice', page.getByRole('dialog'));
    await closeDialog();
  });
  await action('exercise-library', async () => {
    await page.getByRole('tab', { name: 'Exercise Library' }).click();
    await shot('18-exercise-library', 'Catalogue filtrable des exercices');
    await page.getByText('View Technique Cues', { exact: true }).first().click();
    await page.getByRole('dialog').waitFor();
    await page.getByRole('dialog').getByText('Setup & Biomechanics', { exact: true }).waitFor();
    await shot('19-exercise-technique', 'Fiche technique et accès au coach spécialisé', page.getByRole('dialog'));
    await closeDialog();
  });

  await action('tracker', async () => {
    await go('/tracker');
    await page.getByText('Fatigue & Plateau Diagnosis', { exact: true }).waitFor();
    await shot('20-tracker-diagnosis', 'Diagnostic de plateau et prescription calculée');
    await page.getByRole('button', { name: 'Apply Deload (Prefill)', exact: true }).click();
    await page.getByRole('heading', { name: "Today's Session Sets" }).scrollIntoViewIfNeeded();
    await shot('21-deload-draft', 'Décharge : préremplissage des séries avant confirmation');
    await page.getByRole('heading', { name: 'Historical Sessions' }).scrollIntoViewIfNeeded();
    await shot('22-performance-history', 'Courbe de performance et séances enregistrées');
  });

  const mobile = await context.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
  await mobile.waitForTimeout(2000);
  await mobile.screenshot({ path: path.join(output, '23-mobile-dashboard.png'), animations: 'disabled' });
  manifest.screenshots.push({ file: '23-mobile-dashboard.png', title: 'Interface mobile et navigation responsive', route: '/' });
  console.log('CAPTURE 23-mobile-dashboard.png');
} finally {
  if (bearer) await api('/api/auth/me', 'DELETE', { password }).catch(e => console.error('Cleanup:', e.message));
  await fs.writeFile(path.join(output, 'captures.json'), JSON.stringify(manifest, null, 2));
  await browser.close();
  console.log(`Report screenshots: ${manifest.screenshots.filter(s => s.file).length}, failures: ${manifest.screenshots.filter(s => s.error).length}`);
}
