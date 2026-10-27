// Documentation-only renderer. Uses an existing Playwright install and Edge.
// Mermaid is loaded at a fixed version; no application packages are installed.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const version = '11.12.0';
const library = `https://cdn.jsdelivr.net/npm/mermaid@${version}/dist/mermaid.esm.min.mjs`;
const guide = process.argv.includes('--guide');
const assistantForecast = process.argv.includes('--assistant-forecast');
const growthLearning = process.argv.includes('--growth-learning');
const trinityIntegration = process.argv.includes('--trinity-integration');
const loopClosure = process.argv.includes('--loop-closure');
if (process.argv.slice(2).some(argument => !['--guide', '--assistant-forecast', '--growth-learning', '--trinity-integration', '--loop-closure'].includes(argument)) || [guide, assistantForecast, growthLearning, trinityIntegration, loopClosure].filter(Boolean).length > 1) {
  throw new Error('Supported option: --guide OR --assistant-forecast OR --growth-learning OR --trinity-integration OR --loop-closure');
}
const names = loopClosure
  ? ['assistant-loop-closure']
  : trinityIntegration
  ? ['assistant-trinity-integration']
  : growthLearning
  ? ['assistant-growth-regression', 'assistant-knowledge-reuse']
  : assistantForecast
  ? ['assistant-decision-map', 'assistant-improvement-effects', 'assistant-forecast-validation']
  : guide
  ? ['memory-guide-data', 'memory-guide-parallel', 'memory-guide-branches',
     'memory-guide-forget-race', 'memory-guide-reconnect', 'memory-guide-private-output']
  : ['memory-context-architecture', 'memory-context-lifecycle'];
const receipt = loopClosure ? 'closed-loop-render-2026-10-26.json'
  : trinityIntegration ? 'trinity-implementation-render-2026-10-26.json'
  : growthLearning ? 'learning-knowledge-render-2026-10-26.json'
  : assistantForecast ? 'assistant-forecast-render-2026-10-26.json'
  : guide ? 'memory-guide-render-2026-10-23.json' : 'memory-context-render-2026-10-23.json';
const root = path.resolve(__dirname, '..');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const evidence = { renderer: `mermaid@${version}`, library, browser: browser.version(),
    timestamp: new Date().toISOString(), resources: [], diagrams: [] };
  try {
    const page = await browser.newPage({ viewport: { width: 1800, height: 1200 }, deviceScaleFactor: 1.5 });
    const downloads = [];
    page.on('response', response => {
      if (response.url().startsWith(`https://cdn.jsdelivr.net/npm/mermaid@${version}/`)) {
        downloads.push(response.body().then(body => evidence.resources.push({ url: response.url(), sha256: sha(body), bytes: body.length })));
      }
    });
    await page.setContent('<html><head><meta charset="utf-8"></head><body></body></html>');
    await page.evaluate(async url => {
      window.diagramLibrary = (await import(url)).default;
      window.diagramLibrary.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base',
        themeVariables: { fontFamily: 'Microsoft YaHei, sans-serif', fontSize: '17px', primaryColor: '#edf4fa', lineColor: '#617385' },
        flowchart: { htmlLabels: false, curve: 'linear', nodeSpacing: 38, rankSpacing: 48, wrappingWidth: 280, useMaxWidth: false } });
    }, library);
    for (let n = 0; n < names.length; n++) {
      const name = names[n], prefix = path.join(root, 'docs', 'diagrams', name);
      const source = await fs.readFile(prefix + '.mmd', 'utf8');
      const rendered = await page.evaluate(async ({ source, n }) => {
        const { svg } = await window.diagramLibrary.render('drawing' + n, source);
        document.body.innerHTML = svg;
        document.body.style.cssText = 'margin:0;padding:16px;background:white;width:max-content';
        const element = document.querySelector('svg');
        const view = element.viewBox.baseVal;
        element.setAttribute('width', Math.ceil(view.width)); element.setAttribute('height', Math.ceil(view.height));
        return { svg: element.outerHTML, width: Math.ceil(view.width), height: Math.ceil(view.height) };
      }, { source, n });
      await fs.writeFile(prefix + '.svg', rendered.svg);
      await page.setViewportSize({ width: Math.max(900, rendered.width + 32), height: Math.max(800, rendered.height + 32) });
      await page.locator('svg').screenshot({ path: prefix + '.png' });
      evidence.diagrams.push({ name, width: rendered.width, height: rendered.height, source_sha256: sha(source),
        svg_sha256: sha(rendered.svg), png_sha256: sha(await fs.readFile(prefix + '.png')) });
    }
    await Promise.all(downloads);
    await fs.writeFile(path.join(root, 'docs/evidence', receipt), JSON.stringify(evidence, null, 2) + '\n');
    console.log(JSON.stringify(evidence.diagrams));
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
