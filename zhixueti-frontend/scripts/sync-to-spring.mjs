import { cpSync, mkdirSync, rmSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const dist = join(root, 'dist')
const targets = [
  join(root, '..', 'src', 'main', 'resources', 'static'),
  join(root, '..', 'target', 'classes', 'static'),
]

if (!existsSync(join(dist, 'index.html'))) {
  console.error('[sync-to-spring] dist/index.html missing - run vite build first')
  process.exit(1)
}

const indexHtml = readFileSync(join(dist, 'index.html'), 'utf8')

for (const dest of targets) {
  mkdirSync(dest, { recursive: true })
  const assetsDest = join(dest, 'assets')
  if (existsSync(assetsDest)) rmSync(assetsDest, { recursive: true, force: true })
  cpSync(join(dist, 'assets'), assetsDest, { recursive: true })
  writeFileSync(join(dest, 'index.html'), indexHtml)
  writeFileSync(join(dest, 'zhixueti-spa.html'), indexHtml)
  console.log('[sync-to-spring] synced ->', dest)
}
