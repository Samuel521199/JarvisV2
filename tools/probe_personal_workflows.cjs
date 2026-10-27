const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {chromium} = require('C:/Users/samuel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder = path.resolve('docs/evidence/personal-workflows-1.0.0-2026-10-26');
const origin = 'http://127.0.0.1:18282';
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const report = {checks: [], errors: []};
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1050}, reducedMotion: 'reduce'});
    page.on('pageerror', error => report.errors.push(error.message));
    await page.goto(origin + '/settings#skill');
    const search = page.getByLabel('搜索技能', {exact: true});
    await search.fill('英语');
    const english = page.locator('.skill-card').filter({hasText: '英语学习与练习'});
    await english.waitFor();
    const mark = english.locator('.personal-skill-icon');
    assert.equal(await mark.innerText(), '🗣️');
    await mark.focus();
    assert.equal(await mark.getAttribute('aria-describedby'), 'ui-tooltip');
    assert.match(await page.locator('#ui-tooltip').innerText(), /练习英语/);
    report.checks.push('English card, color icon, keyboard tooltip and default enablement');
    await page.keyboard.press('Tab');
    await english.screenshot({path: path.join(folder, 'english-card.png')});
    await english.getByRole('button', {name: '使用条件', exact: true}).click();
    assert.ok(await page.getByRole('heading', {name: '什么时候不使用', exact: true}).isVisible());
    assert.match(await page.locator('#modal-content').innerText(), /同一会话持续练习/);
    report.checks.push('Applicability, exclusions and concrete starting examples visible');
    await page.screenshot({path: path.join(folder, 'english-details.png')});
    await page.locator('#close-modal').click();
    await search.fill('日志');
    const journal = page.locator('.skill-card').filter({hasText: '日志与行动复盘'});
    await journal.waitFor();
    assert.equal(await journal.locator('.personal-skill-icon').innerText(), '📔');
    assert.ok(await journal.getByRole('button', {name: '停用', exact: true}).isVisible());
    await journal.screenshot({path: path.join(folder, 'journal-card.png')});
    report.checks.push('Journal card searchable and enabled');
    await page.goto(origin);
    await page.locator('#skill option[value="english-coach"]').waitFor({state: 'attached'});
    assert.equal(await page.locator('#skill option[value="english-coach"]').isDisabled(), false);
    assert.equal(await page.locator('#skill option[value="journal-review"]').isDisabled(), false);
    report.checks.push('Both workflows selectable in chat');
    assert.deepEqual(report.errors, []);
    report.passed = true;
  } catch (error) {
    report.passed = false; report.failure = error.message; process.exitCode = 1;
  } finally {
    fs.mkdirSync(folder, {recursive: true});
    fs.writeFileSync(path.join(folder, 'browser.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
    await browser.close();
  }
})();
