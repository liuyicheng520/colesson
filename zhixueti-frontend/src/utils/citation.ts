/** Strip trailing「知识依据与参考范围」section from AI answers (lecture Q&A display + TTS). */
export function stripCitationBlock(content: string): string {
  if (!content) return content
  const markers = [
    '## 📚 知识依据与参考范围',
    '📚 **知识依据与参考范围**',
    '📚 知识依据与参考范围',
    '**📚 知识依据与参考范围**',
  ]
  let text = content
  for (const marker of markers) {
    const idx = text.indexOf(marker)
    if (idx !== -1) text = text.slice(0, idx)
  }
  const lines = text.split('\n')
  let cut = lines.length
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim()
    if (s.includes('知识依据') && (s.startsWith('📚') || s.startsWith('##'))) {
      cut = i
      break
    }
    if (s.startsWith('- **知识点依据') || s.startsWith('* **知识点依据')) {
      cut = i
      break
    }
  }
  return lines.slice(0, cut).join('\n').trim()
}
