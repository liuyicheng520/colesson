/**
 * three.js 类型声明补充。
 *
 * 项目仅按需引入少量 three API（`await import('three')`），
 * three 0.170 的构建产物未随包提供类型声明。此处按实际使用面做最小声明，
 * 使全站类型检查不被阻断；如需完整类型可改装 `@types/three` 并删除本文件。
 */
declare module 'three' {
  export type WebGLRenderer = any
  export type Scene = any
  export type PerspectiveCamera = any
  export type Points = any
  export type LineSegments = any
  export type BufferGeometry = any
  export type ShaderMaterial = any
  export type PointsMaterial = any
  export type LineBasicMaterial = any
  export type BufferAttribute = any
  export type Vector3 = any
  export type Color = any
  export type Material = any

  export const WebGLRenderer: any
  export const Scene: any
  export const PerspectiveCamera: any
  export const BufferGeometry: any
  export const BufferAttribute: any
  export const Points: any
  export const LineSegments: any
  export const ShaderMaterial: any
  export const PointsMaterial: any
  export const LineBasicMaterial: any
  export const Vector3: any
  export const Color: any
  export const AdditiveBlending: any
}

declare module 'three/build/three.module.js' {
  export * from 'three'
}
