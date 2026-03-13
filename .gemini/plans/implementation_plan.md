# Novel Translator Project Plan

Focused on creating a tool that translates novels while maintaining narrative tone, character names, and consistent terminology across chapters.

## Project Structure
We will use a per-novel hierarchical structure within `e:\ai-projects\novel-translator`:
- `projects/`: Main directory for all novel projects.
    - `[Novel-Title-In-English]/`: Folder for a specific novel.
        - `source/`: Source files (input chapters).
        - `output/`: Translated chapters.
        - `glossary.json`: Novel-specific terms.
        - `metadata.json`: Original metadata (CN title, URL).
- `.gemini/`: Global persistence for agent plans and shared history.
- `engines/`: Core logic for scraping and translation.

## Proposed Components

### 1. Scraper Engine (New)
* **URL-based Extraction**: Capability to fetch chapter content from popular Chinese novel sites (e.g., 69shuba, qidian, etc.).
* **Search & Scan**: AI-assisted scanning to identify novel availability based on titles or genres.
* **Automatic Folder Creation**: Translate Chinese titles to English for folder naming.

### 2. Translation Engine
* **Context Window Management**: Translate in chunks (paragraphs or scenes).
* **Glossary Integration**: Use the novel-specific `glossary.json`.

### 3. Local Persistence (`.gemini`)
* All `task.md` and `implementation_plan.md` files will be mirrored here.
* `chat_history.txt` will be saved here to track our design decisions.

## Verification Plan
* **Dry Run**: Translate a short chapter and check for terminology consistency.
* **Context Test**: Verify that the AI remembers previous events/names in the current translation chunk.
