import { cp, mkdir, rm } from 'node:fs/promises';

await rm('dist', { recursive: true, force: true });
await mkdir('dist', { recursive: true });
for (const file of ['index.html', 'algorithm.html', 'styles.css', 'app.js', 'algorithm.js', 'push-messages.js', 'data.js']) {
  await cp(file, `dist/${file}`);
}
