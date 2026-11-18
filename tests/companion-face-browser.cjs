const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.JARVIS_PLAYWRIGHT || 'playwright');

(async () => {
  const folder = path.resolve(process.argv[2]);
  const fixture = JSON.parse(fs.readFileSync(path.join(folder, 'fixture.json')));
  const origin = 'http://127.0.0.1:' + fixture.port;
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const report = {passed:false, checks:[], errors:[], model_calls:0, scope:'Isolated owner HTTP fixture with synthetic work'};
  try {
    const context = await browser.newContext({viewport:{width:660, height:720}, deviceScaleFactor:2, reducedMotion:'no-preference'});
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push(error.message));
    await page.addInitScript(() => {
      window.faceAnimations = [];
      window.faceRandom = .15;
      Math.random = () => window.faceRandom;
      const animate = Element.prototype.animate;
      Element.prototype.animate = function (frames, options) {
        if (this.matches('.face-lids, .face-glance')) {
          window.faceAnimations.push({className:this.getAttribute('class'), time:Date.now(), frames:frames.length, duration:options.duration});
        }
        return animate.call(this, frames, options);
      };
    });
    let workState = 'idle';
    await page.route('**/api/work-status', async route => {
      const item = {id:'face-fixture', source:'tasks', title:'合成工作'};
      const statuses = {
        idle:[],
        running:[{...item, state:'running'}],
        unread:[{...item, state:'finished', attention:{unread:true}}],
        unknown:[],
      };
      await route.fulfill({json:{items:statuses[workState], labels:{}, activity:{
        participants:workState === 'unknown' ? [{state:'unknown'}] : [],
      }}});
    });
    await page.clock.install();
    assert.equal((await context.request.post(origin + '/api/local-access', {data:{key:fixture.key}, headers:{Origin:origin}})).status(), 200);
    await page.goto(origin + '/companion');
    await page.waitForSelector('#robot[data-face-motion][data-expression="resting"]');
    const robot = page.locator('#robot');
    const eye = page.locator('.face-eye-left');
    const eyeShape = () => eye.evaluate(node => getComputedStyle(node).d);
    const events = () => page.evaluate(() => window.faceAnimations);
    const box = await robot.boundingBox();
    const rest = await eyeShape();
    assert.notEqual(rest, 'none');
    const pose = async name => robot.screenshot({path:path.join(folder, name + '.png'), animations:'disabled'});
    await pose('resting');

    await page.clock.runFor(3500);
    assert.equal((await events()).length, 0);
    await page.clock.runFor(1100);
    const first = (await events())[0];
    assert.equal(first.className, 'face-lids');
    assert.equal(first.frames, 6);
    assert.ok(first.duration >= 410 && first.duration <= 510);

    await page.evaluate(() => { window.faceRandom = .95; });
    await page.clock.runFor(14000);
    const sample = await events();
    assert.ok(sample.length >= 3);
    assert.equal(sample[1].className, 'face-glance');
    assert.equal(sample[2].className, 'face-glance');
    assert.notEqual(sample[1].time - sample[0].time, sample[2].time - sample[1].time);
    assert.deepEqual(await robot.boundingBox(), box);
    report.checks.push('Variable ambient timing, occasional double blink, and glances leave the button hit region unchanged');

    await page.mouse.move(box.x + 17, box.y + 20);
    assert.equal(await robot.getAttribute('data-expression'), 'curious');
    assert.equal(await robot.getAttribute('data-gaze-x'), 'left');
    await page.mouse.move(box.x + 56, box.y + 21);
    assert.equal(await robot.getAttribute('data-gaze-x'), 'right');
    await pose('curious');
    await page.mouse.click(box.x + 37, box.y + 34);
    assert.equal(await robot.getAttribute('data-expression'), 'acknowledging');
    await page.waitForSelector('#card[data-mode="chat"]:not([hidden])');
    await page.locator('#close-card').click();
    await pose('acknowledging');
    assert.notEqual(await eyeShape(), rest);
    await page.mouse.move(7, 8);
    await page.clock.runFor(900);
    assert.equal(await robot.getAttribute('data-expression'), 'resting');
    report.checks.push('Pointer gaze and brief eye smile acknowledge the click while opening the original chat');

    for (const [underlying, expression] of [['running','focused'], ['unread','attention'], ['unknown','uncertain']]) {
      workState = underlying;
      await page.evaluate(() => window.dispatchEvent(new Event('jarvis:work-viewed')));
      await page.waitForSelector('#robot[data-expression="' + expression + '"]');
      await pose(expression);
    }
    await page.mouse.move(box.x + 15, box.y + 20);
    assert.equal(await robot.getAttribute('data-expression'), 'uncertain');
    assert.equal(await robot.getAttribute('data-gaze-x'), '');
    report.checks.push('Existing work states map to distinct poses and uncertainty takes precedence over pointer play');

    await page.emulateMedia({reducedMotion:'reduce'});
    await page.waitForFunction(() => !document.getElementById('robot').hasAttribute('data-face-motion'));
    const before = (await events()).length;
    await page.clock.runFor(17000);
    assert.equal((await events()).length, before);
    assert.equal(await robot.getAttribute('data-expression'), 'uncertain');
    await page.emulateMedia({reducedMotion:'no-preference'});
    await page.waitForSelector('#robot[data-face-motion]');
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {value:true, configurable:true});
      document.dispatchEvent(new Event('visibilitychange'));
    });
    assert.equal(await robot.getAttribute('data-face-motion'), null);
    await page.clock.runFor(17000);
    assert.equal((await events()).length, before);
    await page.evaluate(() => {
      delete document.hidden;
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await page.waitForSelector('#robot[data-face-motion]');
    report.checks.push('OS reduced motion and hidden page stop decorative animation while preserving semantic poses');
    assert.deepEqual(report.errors, []);
    report.ambient = sample;
    report.passed = true;
  } finally {
    fs.writeFileSync(path.join(folder, 'face-browser.json'), JSON.stringify(report, null, 2) + '\n');
    await browser.close();
  }
  console.log(JSON.stringify(report));
})().catch(error => { console.error(error); process.exitCode = 1; });
