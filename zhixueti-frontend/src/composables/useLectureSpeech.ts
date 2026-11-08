import { ref, onUnmounted } from 'vue'
import { stripForTts } from '@/composables/useTtsPlayer'

/** 按句号/问号等切分口播句，用于聚光灯逐句高亮（参考 OpenMAIC speech 分段） */
export function splitNarration(text: string): string[] {
  const cleaned = stripForTts(text)
  if (!cleaned) return []
  const parts = cleaned.split(/(?<=[。！？；.!?;])/).map((s) => s.trim()).filter(Boolean)
  return parts.length ? parts : [cleaned]
}

function waitForVoices(): Promise<void> {
  if (!('speechSynthesis' in window)) return Promise.resolve()
  return new Promise((resolve) => {
    const synth = window.speechSynthesis
    if (synth.getVoices().length) {
      resolve()
      return
    }
    synth.onvoiceschanged = () => resolve()
    window.setTimeout(resolve, 300)
  })
}

export function useLectureSpeech() {
  const speaking = ref(false)
  const bubbleText = ref('')
  const bubbleRole = ref<'teacher' | 'user' | 'idle'>('idle')
  const activeBulletIndex = ref(-1)
  const activeSentenceIndex = ref(0)

  let cancelled = false
  let gen = 0

  function stop() {
    cancelled = true
    gen += 1
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    speaking.value = false
    activeBulletIndex.value = -1
    activeSentenceIndex.value = 0
  }

  function speakUtterance(text: string, rate: number): Promise<void> {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window) || !text.trim()) {
        resolve()
        return
      }
      const utterance = new SpeechSynthesisUtterance(text.slice(0, 800))
      utterance.lang = 'zh-CN'
      utterance.rate = rate
      const done = () => resolve()
      utterance.onend = done
      utterance.onerror = done
      window.speechSynthesis.speak(utterance)
    })
  }

  async function speakSlide(
    narration: string,
    bulletCount: number,
    rate: number,
    onComplete?: () => void,
  ) {
    stop()
    cancelled = false
    const myGen = ++gen
    const sentences = splitNarration(narration)

    if (!sentences.length) {
      bubbleRole.value = 'idle'
      bubbleText.value = ''
      return
    }

    await waitForVoices()
    speaking.value = true
    bubbleRole.value = 'teacher'

    for (let i = 0; i < sentences.length; i++) {
      if (cancelled || myGen !== gen) return
      activeSentenceIndex.value = i
      bubbleText.value = sentences[i]
      if (bulletCount > 0) {
        activeBulletIndex.value = Math.min(
          bulletCount - 1,
          Math.floor((i / Math.max(1, sentences.length - 1)) * (bulletCount - 1)),
        )
      } else {
        activeBulletIndex.value = -1
      }
      await speakUtterance(sentences[i], rate)
    }

    if (cancelled || myGen !== gen) return
    speaking.value = false
    activeBulletIndex.value = -1
    onComplete?.()
  }

  async function speakReply(text: string, rate: number) {
    const cleaned = stripForTts(text)
    if (!cleaned) return
    stop()
    cancelled = false
    const myGen = gen
    speaking.value = true
    bubbleRole.value = 'teacher'
    bubbleText.value = cleaned
    await waitForVoices()
    if (cancelled || myGen !== gen) return
    await speakUtterance(cleaned.slice(0, 1200), rate)
    if (cancelled || myGen !== gen) return
    speaking.value = false
  }

  onUnmounted(stop)

  return {
    speaking,
    bubbleText,
    bubbleRole,
    activeBulletIndex,
    activeSentenceIndex,
    speakSlide,
    speakReply,
    stop,
  }
}
