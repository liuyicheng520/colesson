import { ref, onUnmounted } from 'vue'

function stripForTts(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/\$\$[\s\S]*?\$\$/g, '')
    .replace(/\$[^$]+\$/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[#>*\-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function useTtsPlayer(defaultRate = 1) {
  const playingId = ref<string | null>(null)
  const progress = ref(0)
  const paused = ref(false)
  const rate = ref(defaultRate)

  let progressTimer: ReturnType<typeof setInterval> | null = null
  let startTime = 0
  let estimatedMs = 0
  let currentUtterance: SpeechSynthesisUtterance | null = null

  function clearTimer() {
    if (progressTimer) {
      clearInterval(progressTimer)
      progressTimer = null
    }
  }

  function stop() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    clearTimer()
    playingId.value = null
    progress.value = 0
    paused.value = false
    currentUtterance = null
  }

  function play(id: string, rawText: string) {
    if (!('speechSynthesis' in window)) return
    const text = stripForTts(rawText)
    if (!text) return

    if (playingId.value === id && paused.value) {
      window.speechSynthesis.resume()
      paused.value = false
      return
    }

    stop()
    currentUtterance = new SpeechSynthesisUtterance(text.slice(0, 3000))
    currentUtterance.lang = 'zh-CN'
    currentUtterance.rate = rate.value
    playingId.value = id
    estimatedMs = Math.max(3000, (text.length / rate.value) * 120)
    startTime = Date.now()
    progressTimer = setInterval(() => {
      const elapsed = Date.now() - startTime
      progress.value = Math.min(99, (elapsed / estimatedMs) * 100)
    }, 150)

    currentUtterance.onend = () => {
      progress.value = 100
      clearTimer()
      playingId.value = null
      paused.value = false
    }
    currentUtterance.onerror = () => stop()
    window.speechSynthesis.speak(currentUtterance)
  }

  function pause() {
    if (!playingId.value || !('speechSynthesis' in window)) return
    window.speechSynthesis.pause()
    paused.value = true
    clearTimer()
  }

  function toggle(id: string, text: string) {
    if (playingId.value === id && !paused.value) {
      pause()
    } else {
      play(id, text)
    }
  }

  onUnmounted(stop)

  return { playingId, progress, paused, rate, play, pause, stop, toggle }
}

export { stripForTts }
