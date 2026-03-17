<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const novels = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
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
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-4 py-4">
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Novel Reader</h1>
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
          class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 cursor-pointer hover:border-violet-400 dark:hover:border-violet-500 hover:shadow-md transition-all"
        >
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
          <div class="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
            <span>{{ novel.source_language }} → {{ novel.target_language }}</span>
            <span>{{ novel.translated_count }}{{ novel.total_chapters ? ` / ${novel.total_chapters}` : '' }} ch</span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
