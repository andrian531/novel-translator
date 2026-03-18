<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSettings } from '../composables/useSettings'
import { saveProgress } from '../composables/useProgress'

const router = useRouter()
const route = useRoute()
const { dark, fontSize } = useSettings()

const chapter = ref(null)
const novel = ref(null)
const loading = ref(true)
const error = ref('')
const sidebarOpen = ref(true)
const sidebarRef = ref(null)

async function loadNovel(projectId) {
  const res = await fetch(`/api/novels/${projectId}`)
  if (!res.ok) throw new Error('Novel not found')
  novel.value = await res.json()
}

async function loadChapter(projectId, filename) {
  loading.value = true
  error.value = ''
  chapter.value = null
  try {
    const res = await fetch(`/api/novels/${projectId}/chapters/${filename}`)
    if (!res.ok) throw new Error('Chapter not found')
    chapter.value = await res.json()
    saveProgress(projectId, filename)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([
      loadNovel(route.params.id),
      loadChapter(route.params.id, route.params.filename),
    ])
  } catch (e) {
    error.value = e.message
    loading.value = false
  }
  scrollSidebarToActive()
})

watch(() => route.params.filename, async (f) => {
  if (f) {
    await loadChapter(route.params.id, f)
    scrollSidebarToActive()
    window.scrollTo({ top: 0 })
  }
})

function scrollSidebarToActive() {
  nextTick(() => {
    const el = sidebarRef.value?.querySelector('.sidebar-active')
    if (el) el.scrollIntoView({ block: 'nearest' })
  })
}

// Keyboard navigation
function onKeyDown(e) {
  if (!chapter.value) return
  if (e.key === 'ArrowRight' && chapter.value.next) {
    router.push(`/novel/${route.params.id}/chapter/${chapter.value.next}`)
  }
  if (e.key === 'ArrowLeft' && chapter.value.prev) {
    router.push(`/novel/${route.params.id}/chapter/${chapter.value.prev}`)
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))

function chapterLabel(filename) {
  const m = filename.match(/(\d+)/)
  return m ? `Chapter ${parseInt(m[1])}` : filename.replace('.txt', '')
}

function paragraphs(text) {
  return text.split(/\n+/).filter(p => p.trim())
}

const novelTitle = computed(() => {
  if (!novel.value) return ''
  return novel.value.title_translated || novel.value.title
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex">

    <!-- Sidebar -->
    <aside
      :class="[
        'fixed top-0 left-0 h-full z-20 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-0 overflow-hidden'
      ]"
    >
      <div class="px-4 py-4 border-b border-gray-100 dark:border-gray-700 shrink-0">
        <button
          @click="router.push(`/novel/${route.params.id}`)"
          class="text-xs text-violet-600 dark:text-violet-400 hover:underline mb-1 block"
        >← Novel</button>
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-snug line-clamp-2">
          {{ novelTitle }}
        </h2>
        <p v-if="novel" class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          {{ novel.chapters?.length }} chapters
        </p>
      </div>

      <nav ref="sidebarRef" class="flex-1 overflow-y-auto py-2">
        <button
          v-for="ch in novel?.chapters ?? []"
          :key="ch"
          @click="router.push(`/novel/${route.params.id}/chapter/${ch}`)"
          :class="[
            'w-full text-left px-4 py-2 text-sm transition-colors',
            ch === route.params.filename
              ? 'sidebar-active bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 font-medium'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-gray-100'
          ]"
        >
          {{ chapterLabel(ch) }}
        </button>
      </nav>
    </aside>

    <!-- Main -->
    <div :class="['flex-1 flex flex-col transition-all duration-300', sidebarOpen ? 'ml-64' : 'ml-0']">
      <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div class="max-w-2xl mx-auto px-4 py-3 flex items-center gap-2">
          <!-- Sidebar toggle -->
          <button
            @click="sidebarOpen = !sidebarOpen"
            class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors p-1 -ml-1 shrink-0"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </button>

          <span v-if="chapter" class="text-sm text-gray-500 dark:text-gray-400 truncate flex-1">
            {{ chapterLabel(route.params.filename) }}
            <span class="text-gray-300 dark:text-gray-600 mx-1">·</span>
            {{ chapter.index }} / {{ chapter.total }}
          </span>

          <!-- Font size controls -->
          <div class="flex items-center gap-1 shrink-0">
            <button
              @click="fontSize = Math.max(13, fontSize - 1)"
              class="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors text-sm font-mono"
              title="Smaller text"
            >A−</button>
            <button
              @click="fontSize = Math.min(24, fontSize + 1)"
              class="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors text-sm font-mono"
              title="Larger text"
            >A+</button>
          </div>

          <!-- Dark mode toggle -->
          <button
            @click="dark = !dark"
            class="p-1.5 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shrink-0"
          >
            <svg v-if="dark" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
            </svg>
            <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
            </svg>
          </button>
        </div>
      </header>

      <main class="max-w-2xl mx-auto w-full px-4 py-10">
        <div v-if="loading" class="flex justify-center py-20">
          <div class="w-8 h-8 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
        </div>

        <div v-else-if="error" class="text-center py-20 text-red-500">{{ error }}</div>

        <template v-else-if="chapter">
          <h1 v-if="chapter.title" class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-8 leading-snug">
            {{ chapter.title }}
          </h1>

          <article>
            <p
              v-for="(para, i) in paragraphs(chapter.content)"
              :key="i"
              class="text-gray-800 dark:text-gray-200 leading-relaxed mb-5"
              :style="{ fontSize: fontSize + 'px' }"
            >{{ para }}</p>
          </article>

          <!-- Keyboard hint -->
          <p class="text-xs text-gray-300 dark:text-gray-600 text-center mt-8 mb-2">
            ← → arrow keys to navigate chapters
          </p>

          <!-- Bottom navigation -->
          <div class="flex gap-3 mt-4 pt-6 border-t border-gray-200 dark:border-gray-700">
            <button
              v-if="chapter.prev"
              @click="router.push(`/novel/${route.params.id}/chapter/${chapter.prev}`)"
              class="flex-1 py-3 px-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm text-gray-700 dark:text-gray-300 hover:border-violet-400 dark:hover:border-violet-500 hover:text-violet-700 dark:hover:text-violet-300 transition-all"
            >
              ← Previous
            </button>
            <div v-else class="flex-1"></div>

            <button
              v-if="chapter.next"
              @click="router.push(`/novel/${route.params.id}/chapter/${chapter.next}`)"
              class="flex-1 py-3 px-4 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm text-white font-medium transition-colors"
            >
              Next →
            </button>
            <div v-else class="flex-1"></div>
          </div>
        </template>
      </main>
    </div>

  </div>
</template>
