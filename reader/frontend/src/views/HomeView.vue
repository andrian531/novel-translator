<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSettings } from '../composables/useSettings'
import { getAllProgress } from '../composables/useProgress'

const router = useRouter()
const novels = ref([])
const loading = ref(true)
const error = ref('')
const progress = ref({})
const { dark } = useSettings()

onMounted(async () => {
  progress.value = getAllProgress()
  try {
    const res = await fetch('/api/novels')
    if (!res.ok) throw new Error('Failed to load novels')
    novels.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function ratingColor(rating) {
  if (rating === 'adult') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (rating === 'mature') return 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300'
  return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
}

function chapterLabel(filename) {
  const m = filename?.match(/(\d+)/)
  return m ? `Chapter ${parseInt(m[1])}` : filename?.replace('.txt', '') ?? ''
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Novel Reader</h1>
        <!-- Dark mode toggle -->
        <button
          @click="dark = !dark"
          class="p-2 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          :title="dark ? 'Light mode' : 'Dark mode'"
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

    <main class="max-w-5xl mx-auto px-4 py-8">
      <div v-if="loading" class="flex justify-center py-20">
        <div class="w-8 h-8 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <div v-else-if="error" class="text-center py-20 text-red-500">{{ error }}</div>

      <div v-else-if="novels.length === 0" class="text-center py-20 text-gray-400">
        No translated novels found.
      </div>

      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="novel in novels"
          :key="novel.id"
          @click="router.push(`/novel/${novel.id}`)"
          class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 cursor-pointer hover:border-violet-400 dark:hover:border-violet-500 hover:shadow-md transition-all flex flex-col overflow-hidden"
        >
          <!-- Cover image -->
          <div class="w-full h-40 bg-gray-100 dark:bg-gray-700 shrink-0 overflow-hidden">
            <img
              v-if="novel.has_cover"
              :src="`/api/novels/${novel.id}/cover`"
              :alt="novel.title_translated || novel.title"
              class="w-full h-full object-cover"
            />
            <div v-else class="w-full h-full flex items-center justify-center text-gray-300 dark:text-gray-600">
              <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
              </svg>
            </div>
          </div>

          <div class="p-5 flex flex-col flex-1">
          <div class="flex items-start justify-between gap-2 mb-2">
            <div class="leading-snug">
              <h2 class="font-semibold text-gray-900 dark:text-gray-100">{{ novel.title_translated || novel.title }}</h2>
              <p v-if="novel.title_translated && novel.title_translated !== novel.title" class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ novel.title }}</p>
            </div>
            <span :class="ratingColor(novel.content_rating)" class="text-xs px-2 py-0.5 rounded-full shrink-0 capitalize">
              {{ novel.content_rating }}
            </span>
          </div>
          <p v-if="novel.author" class="text-sm text-gray-500 dark:text-gray-400 mb-3">{{ novel.author }}</p>
          <p v-if="novel.synopsis" class="text-sm text-gray-600 dark:text-gray-300 line-clamp-3 mb-4">{{ novel.synopsis }}</p>

          <div class="mt-auto flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
            <span>{{ novel.source_language }} → {{ novel.target_language }}</span>
            <span>{{ novel.translated_count }}{{ novel.total_chapters ? ` / ${novel.total_chapters}` : '' }} ch</span>
          </div>

          <!-- Continue reading badge -->
          <div
            v-if="progress[novel.id]"
            @click.stop="router.push(`/novel/${novel.id}/chapter/${progress[novel.id]}`)"
            class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 flex items-center gap-2 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300"
          >
            <svg class="w-3.5 h-3.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
            </svg>
            Continue: {{ chapterLabel(progress[novel.id]) }}
          </div>
          </div><!-- /p-5 inner -->
        </div>
      </div>
    </main>
  </div>
</template>
