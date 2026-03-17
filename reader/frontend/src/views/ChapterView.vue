<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const chapter = ref(null)
const loading = ref(true)
const error = ref('')

async function loadChapter(projectId, filename) {
  loading.value = true
  error.value = ''
  chapter.value = null
  try {
    const res = await fetch(`/api/novels/${projectId}/chapters/${filename}`)
    if (!res.ok) throw new Error('Chapter not found')
    chapter.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => loadChapter(route.params.id, route.params.filename))

watch(() => route.params.filename, (f) => {
  if (f) loadChapter(route.params.id, f)
})

function paragraphs(text) {
  return text.split(/\n+/).filter(p => p.trim())
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
        <button @click="router.push(`/novel/${route.params.id}`)" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors shrink-0">
          ← Chapters
        </button>
        <span v-if="chapter" class="text-gray-500 dark:text-gray-400 text-sm truncate">
          {{ chapter.index }} / {{ chapter.total }}
        </span>
      </div>
    </header>

    <main class="max-w-2xl mx-auto px-4 py-10">
      <div v-if="loading" class="flex justify-center py-20">
        <div class="w-8 h-8 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <div v-else-if="error" class="text-center py-20 text-red-500">{{ error }}</div>

      <template v-else-if="chapter">
        <h1 v-if="chapter.title" class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-8 leading-snug">
          {{ chapter.title }}
        </h1>

        <article class="prose-reading">
          <p
            v-for="(para, i) in paragraphs(chapter.content)"
            :key="i"
            class="text-gray-800 dark:text-gray-200 leading-relaxed mb-5 text-[17px]"
          >{{ para }}</p>
        </article>

        <!-- Navigation -->
        <div class="flex gap-3 mt-12 pt-6 border-t border-gray-200 dark:border-gray-700">
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
</template>
