#!/usr/bin/env node
/**
 * 无头 Chromium CDP 截图：导航 → 可选文本替换 → 滚动到目标位置 → 截取视口。
 *
 * 滚动后再截（而非整页截图），固定侧栏才会停在视口里；整页截图会把 sticky 元素留在文档顶部。
 *
 * 用法：node cdp_shot.mjs <url> <out.png> [scrollY] [width] [height] [from=>to]
 * 依赖：Node ≥22（内置 WebSocket）+ 本机 Chromium（`CHROME_BIN` 指定），无需 playwright。
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [url, out, scrollY = '0', width = '1440', height = '940', replaceSpec = ''] = process.argv.slice(2);

if (!url || !out) {
  console.error('  [ERR] 用法：node cdp_shot.mjs <url> <out.png> [scrollY] [width] [height] [from=>to]');
  process.exit(2);
}

const CHROME = process.env.CHROME_BIN || '';
if (!CHROME || !existsSync(CHROME)) {
  console.error(`  [ERR] 未找到 Chromium（CHROME_BIN=${CHROME || '(空)'}），用 --chrome 或环境变量指定`);
  process.exit(1);
}

const profile = mkdtempSync(join(tmpdir(), 'shot-profile-'));
const port = 9200 + Math.floor(Math.random() * 300);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const chrome = spawn(CHROME, [
  '--headless=new',
  '--disable-gpu',
  '--no-sandbox',
  '--hide-scrollbars',
  `--user-data-dir=${profile}`,
  `--remote-debugging-port=${port}`,
  `--window-size=${width},${height}`,
  'about:blank',
], { stdio: 'ignore' });

async function cdpTarget() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const list = await response.json();
      const page = list.find((target) => target.type === 'page');
      if (page) return page;
    } catch {
      /* 调试端口尚未就绪 */
    }
    await sleep(250);
  }
  throw new Error('CDP 调试端口未就绪');
}

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(wsUrl);
    let nextId = 0;
    const pending = new Map();
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id && pending.has(message.id)) {
        const { ok, fail } = pending.get(message.id);
        pending.delete(message.id);
        message.error ? fail(new Error(JSON.stringify(message.error))) : ok(message.result);
      }
    };
    socket.onerror = (error) => reject(error);
    socket.onopen = () => resolve({
      send(method, params = {}) {
        nextId += 1;
        const id = nextId;
        return new Promise((ok, fail) => {
          pending.set(id, { ok, fail });
          socket.send(JSON.stringify({ id, method, params }));
        });
      },
      close() { socket.close(); },
    });
  });
}

try {
  const target = await cdpTarget();
  const client = await connect(target.webSocketDebuggerUrl);
  await client.send('Page.enable');
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: Number(width), height: Number(height), deviceScaleFactor: 1, mobile: false,
  });
  await client.send('Page.navigate', { url });
  await sleep(2500); // 图表渲染（Chart.js 需一帧以上）
  if (replaceSpec) {
    const [from, to = ''] = replaceSpec.split('=>');
    await client.send('Runtime.evaluate', {
      expression: `(() => {
        const from = ${JSON.stringify(from)}, to = ${JSON.stringify(to)};
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const node = walker.currentNode;
          if (node.nodeValue && node.nodeValue.includes(from)) {
            node.nodeValue = node.nodeValue.split(from).join(to);
          }
        }
        return 1;
      })()`,
    });
    await sleep(200);
  }
  await client.send('Runtime.evaluate', { expression: `window.scrollTo(0, ${Number(scrollY)}); 1` });
  await sleep(900);
  const shot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(out, Buffer.from(shot.data, 'base64'));
  client.close();
  console.log(`  [OK] ${out} scrollY=${scrollY}`);
} catch (error) {
  console.error(`  [ERR] 截图失败：${error && error.message ? error.message : error}`);
  process.exitCode = 1;
} finally {
  chrome.kill('SIGTERM');
}
