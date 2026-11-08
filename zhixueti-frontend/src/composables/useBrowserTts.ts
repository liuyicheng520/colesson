import { ref, onBeforeUnmount } from 'vue'

function stripForTts(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/\*\*/g, '')
    .replace(/[#>*\-_`]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function useBrowserTts() {
  const speaking = ref(false)
  let utter: SpeechSynthesisUtterance | null = null
  let gen = 0

  function stop() {
    gen += 1
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    speaking.value = false
    utter = null
  }

  function speak(raw: string): Promise<void> {
    stop()
    if (!('speechSynthesis' in window)) return Promise.resolve()
    const text = stripForTts(raw)
    if (!text) return Promise.resolve()
    const my = gen
    return new Promise((resolve) => {
      utter = new SpeechSynthesisUtterance(text.slice(0, 3000))
      utter.lang = 'zh-CN'
      utter.rate = 1
      speaking.value = true
      utter.onend = () => {
        if (my === gen) speaking.value = false
        resolve()
      }
      utter.onerror = () => {
        if (my === gen) speaking.value = false
        resolve()
      }
      window.speechSynthesis.speak(utter)
    })
  }

  onBeforeUnmount(stop)

  return { speaking, speak, stop }
}
