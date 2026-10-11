# PastySpace

A tiny write-once pastebin. No accounts. Visit any URL to claim it, or hit **New paste** for a random
three-word URL (EFF wordlist, about 6,200 words, roughly 240 billion combinations). Once a paste is saved, it can't be changed.

- Text and code with syntax highlighting (auto-detect or pick a language), Markdown, and sandboxed rendered HTML
- Rich text pasted from Word or web pages can be converted to Markdown
- Paste screenshots straight from the clipboard, drag and drop files anywhere, or use the file picker
- Images, video and audio display inline. Other files get a download link.
- Everything is stored base64-encoded in SQLite. Data is ephemeral by design.

## Run

    docker compose up -d --build        # http://<host>:8000

Env vars: `PASTY_MAX_MB` (default 50) sets the upload limit. `PASTY_DB` (default `/data/pastyspace.db`) sets the database path.
To wipe all pastes, run `docker compose down -v`.

## CLI

    echo hi | curl --data-binary @- http://host:8000/            # random URL
    cat x.txt | curl --data-binary @- http://host:8000/my-name   # claim a URL (409 if taken)
    curl -F file=@shot.png -F body="notes" http://host:8000/     # files plus optional text
    curl http://host:8000/raw/my-name
