import { ref, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'

type SpeechRec = {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: SpeechRecognitionEventLike) => void) | null
  onerror: ((e: { error?: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>
}

function getSpeechRecognitionCtor(): (new () => SpeechRec) | null {
  const w = window as unknown as Record<string, unknown>
  return (w.SpeechRecognition || w.webkitSpeechRecognition) as (new () => SpeechRec) | null
}

export function useBrowserStt(options?: {
  continuous?: boolean
  onInterim?: (text: string) => void
  onFinal?: (text: string) => void
  onSpeechStart?: () => void
}) {
  const listening = ref(false)
  const interim = ref('')
  const supported = !!getSpeechRecognitionCtor()
  let recognition: SpeechRec | null = null
  let intentionalStop = false

  function start() {
    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) {
      ElMessage.warning('当前浏览器不支持语音识别，请使用 Chrome / Edge')
      return false
    }
    stop()
    intentionalStop = false
    recognition = new Ctor()
    recognition.lang = 'zh-CN'
    recognition.continuous = options?.continuous ?? false
    recognition.interimResults = true
    recognition.onresult = (e) => {
      let interimText = ''
      let finalText = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const row = e.results[i]
        const t = row[0]?.transcript || ''
        if (row.isFinal) finalText += t
        else interimText += t
      }
      if (interimText) {
        interim.value = interimText
        options?.onInterim?.(interimText)
        if (interimText.replace(/\s/g, '').length >= 2) options?.onSpeechStart?.()
      }
      if (finalText.trim()) {
        interim.value = ''
        options?.onFinal?.(finalText.trim())
      }
    }
    recognition.onerror = () => {
      listening.value = false
    }
    recognition.onend = () => {
      listening.value = false
      if (!intentionalStop && options?.continuous && recognition) {
        try {
          recognition.start()
          listening.value = true
        } catch {
          /* ignore restart races */
        }
      }
    }
    try {
      recognition.start()
      listening.value = true
      return true
    } catch {
      listening.value = false
      return false
    }
  }

  function stop() {
    intentionalStop = true
    interim.value = ''
    if (recognition) {
      try {
        recognition.onend = null
        recognition.stop()
      } catch {
        try {
          recognition.abort()
        } catch {
          /* ignore */
        }
      }
      recognition = null
    }
    listening.value = false
  }

  onBeforeUnmount(stop)

  return { listening, interim, supported, start, stop }
}
