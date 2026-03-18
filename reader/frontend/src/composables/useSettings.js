import { ref, watch } from 'vue'

// Module-level singletons — shared across all components
const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
const stored = localStorage.getItem('reader_dark')
const dark = ref(stored !== null ? stored === 'true' : systemDark)

const fontSize = ref(parseInt(localStorage.getItem('reader_font_size') || '17'))

// Apply dark class to <html> immediately
document.documentElement.classList.toggle('dark', dark.value)

watch(dark, (v) => {
  localStorage.setItem('reader_dark', String(v))
  document.documentElement.classList.toggle('dark', v)
})

watch(fontSize, (v) => {
  localStorage.setItem('reader_font_size', String(v))
})

export function useSettings() {
  return { dark, fontSize }
}
