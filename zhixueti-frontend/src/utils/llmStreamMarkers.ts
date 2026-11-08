/** 剥离 LLM 流式通道标记（\x01C\x01 / \x01T\x01），避免渲染成 □ 乱码。 */
export function stripLlmStreamMarkers(text: string): string {
  if (!text) return ''
  return text.replace(/\x01[TC]\x01/g, '').replace(/\x01/g, '')
}
