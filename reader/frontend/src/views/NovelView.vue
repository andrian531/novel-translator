<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSettings } from '../composables/useSettings'
import { getProgress } from '../composables/useProgress'

const router = useRouter()
const route = useRoute()
const novel = ref(null)
const loading = ref(true)
const error = ref('')
const lastChapter = ref(null)
const { dark } = useSettings()

onMounted(async () => {
  lastChapter.value = getProgress(route.params.id)
  try {
    const res = await fetch(`/api/novels/${route.params.id}`)
    if (!res.ok) throw new Error('Novel not found')
    novel.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function chapterLabel(filename) {
  const m = filename.match(/(\d+)/)
  return m ? `Chapter ${parseInt(m[1])}` : filename.replace('.txt', '')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="max-w-3xl mx-auto px-4 py-4 flex items-center gap-3">
        <button @click="router.push('/')" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors">
          ← Back
        </button>
        <span class="text-gray-300 dark:text-gray-600">|</span>
        <span class="text-gray-600 dark:text-gray-300 truncate text-sm flex-1">{{ novel ? (novel.title_translated || novel.title) : '...' }}</span>
        <!-- Dark mode toggle -->
        <button
          @click="dark = !dark"
          class="p-2 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shrink-0"
        >
          <svg v-if="dark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
          </svg>
        </button>
      </div>
    </header>

    <main class="max-w-3xl mx-auto px-4 py-8">
      <div v-if="loading" class="flex justify-center py-20">
        <div class="w-8 h-8 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <div v-else-if="error" class="text-center py-20 text-red-500">{{ error }}</div>

      <template v-else-if="novel">
        <!-- Novel info -->
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-0.5">{{ novel.title_translated || novel.title }}</h1>
          <p v-if="novel.title_translated && novel.title_translated !== novel.title" class="text-sm text-gray-400 dark:text-gray-500 mb-1">{{ novel.title }}</p>
          <p v-if="novel.author" class="text-gray-500 dark:text-gray-400 mb-3">{{ novel.author }}</p>
          <div class="flex flex-wrap gap-2 text-sm mb-4">
            <span class="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-3 py-1 rounded-full">
              {{ novel.source_language }} → {{ novel.target_language }}
            </span>
            <span class="bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 px-3 py-1 rounded-full">
              {{ novel.chapters.length }}{{ novel.total_chapters ? ` / ${novel.total_chapters}` : '' }} chapters
            </span>
          </div>
          <p v-if="novel.synopsis" class="text-gray-600 dark:text-gray-300 leading-relaxed">{{ novel.synopsis }}</p>

          <!-- Continue reading button -->
          <button
            v-if="lastChapter"
            @click="router.push(`/novel/${novel.id}/chapter/${lastChapter}`)"
            class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm rounded-lg font-medium transition-colors"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
            </svg>
            Continue: {{ chapterLabel(lastChapter) }}
          </button>
        </div>

        <!-- Chapter list -->
        <div v-if="novel.chapters.length === 0" class="text-center py-10 text-gray-400">
          No translated chapters yet.
        </div>

        <div v-else class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
          <button
            v-for="ch in novel.chapters"
            :key="ch"
            @click="router.push(`/novel/${novel.id}/chapter/${ch}`)"
            :class="[
              'w-full text-left px-5 py-3 transition-colors text-sm flex items-center justify-between gap-3',
              ch === lastChapter
                ? 'bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-violet-50 dark:hover:bg-violet-900/20 hover:text-violet-700 dark:hover:text-violet-300'
            ]"
          >
            <span>{{ chapterLabel(ch) }}</span>
            <svg v-if="ch === lastChapter" class="w-3.5 h-3.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
            </svg>
          </button>
        </div>
      </template>
    </main>
  </div>
</template>
