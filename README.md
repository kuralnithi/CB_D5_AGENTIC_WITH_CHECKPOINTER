---
sdk: docker
app_port: 7860
---

# FinBot API 🚀
AI-powered Financial Analyst API ready for Hugging Face Spaces.

## ⚠️ Deployment: Mistakes to Avoid

To ensure your backend survives the Hugging Face Linux container environment, keep these critical tips in mind:

### 1. The "Invisible" Newline Trap
When pasting your `DATABASE_URL` or `GROQ_API_KEY` into Hugging Face **Secrets**, do NOT press "Enter" after pasting. This adds an invisible newline character (`\n`) that will cause connection errors.
- **Fix**: Our code now auto-strips newlines, but it's best to always check the secret value.

### 2. Windows Line Endings (`\r\n`)
`startup.sh` must use **Unix (LF)** line endings. If you edit it on Windows and it automatically converts to CRLF, the container will crash with: `/bin/bash^M: bad interpreter`.
- **Fix**: Use VS Code's status bar to set line endings to **LF** before saving.

### 3. Missing the "p" in PostgreSQL
A common copy-paste error is missing the first character of the URL (`ostgresql://`). 
- **Fix**: Always double-check your `DATABASE_URL` secret. It must start exactly with `postgresql://`.

### 4. Neon-Specific Gotchas
If you're using Neon as your cloud database:
- **Use `sslmode=require`**: Without this, the connection will be blocked.
- **Remove `channel_binding=require`**: Neon's connection pooler does not support SCRAM channel binding. Your URL should end with `?sslmode=require`.

### 5. Port Binding
Hugging Face requires your app to listen on **Port 7860** and **Address 0.0.0.0**. Any other port will cause a "Starting..." hang.

## Quick Start
1. Add Secrets to Hugging Face: `DATABASE_URL`, `GROQ_API_KEY`.
2. Push your code: `git push origin master:main`.
3. Watch the logs! 📈
