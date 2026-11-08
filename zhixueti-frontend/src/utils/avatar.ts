/** Resolve avatar URL with optional cache-bust version. */

export function resolveAvatarUrl(url: string | null | undefined, version?: number): string | undefined {
  if (!url) return undefined
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return version ? `${url}${url.includes('?') ? '&' : '?'}_v=${version}` : url
  }
  const base = url.split('?')[0]
  const params = new URLSearchParams(url.includes('?') ? url.split('?')[1] : '')
  if (version) params.set('_v', String(version))
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

/** Client-side center-crop to square and resize before upload. */
export async function prepareAvatarFile(file: File, size = 256): Promise<File> {
  const objectUrl = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('图片加载失败'))
      el.src = objectUrl
    })
    const side = Math.min(img.width, img.height)
    const sx = (img.width - side) / 2
    const sy = (img.height - side) / 2
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法处理图片')
    ctx.drawImage(img, sx, sy, side, side, 0, 0, size, size)
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('图片处理失败'))),
        file.type === 'image/png' ? 'image/png' : 'image/jpeg',
        0.9,
      )
    })
    const ext = file.type === 'image/png' ? 'png' : 'jpg'
    return new File([blob], `avatar.${ext}`, { type: blob.type })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}
