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

## 🛠️ Troubleshooting: Real Problems We Solved

Here are the exact issues we hit during development and how they are fixed in the current code:

### 1. Memory Crash (`INVALID_CHAT_HISTORY`)
*   **The Problem:** If the AI got interrupted while thinking (e.g., a tool timed out), the database session would get "stuck." Any new message you sent for that same session would cause a **500 Internal Server Error.**
*   **The Fix:** We added a **Self-Healing rescue mechanism** in `agent_service.py`. Now, if the backend sees a corrupted thread, it instantly creates a fresh rescue session so your app never crashes!

### 2. "I Forgot My Last Query"
*   **The Problem:** Because everyone was sharing the same "default" ID, the memory was a mess! Also, when a session broke, it had to restart from zero. 
*   **The Fix:** We integrated **Clerk Auth**. Now, the moment you sign in, your chat memory is tied to your **Unique User ID**. Your AI will remember your specific conversations even if you close the tab and come back later.

### 3. Database "Connection Closed" (Neon Fix)
*   **The Problem:** When the AI was thinking hard (reaching out to Groq or searching Google), the Neon database would think the connection was "idle" and kill it. This caused the tool result saving to fail.
*   **The Fix:** We injected **TCP Keep-Alives** directly into the `database.py` connection string. The app now "pings" the database every few seconds while the AI is thinking to keep the line open.

### 4. Running Locally vs Online
*   **The Problem:** Moving code between target environments (Hugging Face vs Localhost) often breaks API connections.
*   **The Fix:** We centralized the **VITE_API_URL** and updated the **CORS** policy to allow the frontend to talk to the backend on `localhost:8000` or the production cloud URL seamlessly.

## 🚀 Quick Start
1.  **Frontend:** Update your `.env` with `VITE_CLERK_PUBLISHABLE_KEY` and `VITE_API_URL`.
2.  **Backend:** Add `DATABASE_URL`, `GROQ_API_KEY`, and `SERPAPI_API_KEY` to your secrets (Local or Cloud).
3.  **Run:** Open two terminals...
    *   `npm run dev` (Frontend)
    *   `uvicorn main:app --reload` (Backend)
4.  **Login & Enjoy!** 📈
