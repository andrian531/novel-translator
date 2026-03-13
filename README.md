# Novel Translator

A tool for translating novels with context awareness and terminology consistency.

## Project Structure
- `projects/`: Root folder for each novel project.
    - `[Novel-Title-In-English]/`: Folder for a specific novel.
        - `source/`: Original source files (chapters).
        - `output/`: Translated results.
        - `glossary.json`: Terminology and names for this specific novel.
- `.gemini/`: Global plans and history.
- `engines/`: Core logic for scraping and translation.

## Getting Started
1. Create a folder for your novel in `projects/` using an English name.
2. Put source chapters (TXT/MD) in the `source/` folder.
3. Or use the scraper engine to fetch chapters directly from URLs.
