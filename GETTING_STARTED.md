# DEFENDER AI — Getting Started

A step-by-step guide to running the Public Defender AI Assistant on your computer.

---

## Option A: One-Click Launch (Recommended)

### What you need first

1. **Node.js 18+** — Download from [nodejs.org](https://nodejs.org) (choose the LTS version)
2. **Python 3.11+** — Download from [python.org](https://python.org)

### Starting the app

**On Mac:**
1. Open Finder and navigate to the DEFENDER-AI folder
2. Double-click `start.sh`
   - If it doesn't open, right-click → Open With → Terminal
3. The app will open in your browser automatically

**On Windows:**
1. Open File Explorer and navigate to the DEFENDER-AI folder
2. Double-click `start.bat`
3. The app will open in your browser automatically

**To stop:** Close the terminal/command prompt window, or press `Ctrl+C`.

---

## Option B: Docker (No Node.js/Python install needed)

### What you need first

1. **Docker Desktop** — Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

### Starting the app

**On Mac:**
1. Open Docker Desktop (make sure it's running)
2. Double-click `start-docker.sh` in the DEFENDER-AI folder
3. The app will open at [http://localhost:3000](http://localhost:3000)

**On Windows:**
1. Open Docker Desktop (make sure it's running)
2. Double-click `start-docker.bat` in the DEFENDER-AI folder
3. The app will open at [http://localhost:3000](http://localhost:3000)

**To stop:** Close the terminal window, or press `Ctrl+C`.

---

## Using the App

1. **Log in** at [http://localhost:3000/login](http://localhost:3000/login)
   - Use any email/password for the MVP demo
2. **Upload a charging document** (PDF or image) on the Upload page
3. **View your case** — the system will process the document through the agent pipeline
4. **Review agent outputs** — each agent's results appear as they complete
5. **Attorney review** — approve or annotate each section before finalizing

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Node.js is not installed" | Download from [nodejs.org](https://nodejs.org) and restart your computer |
| "Python is not installed" | Download from [python.org](https://python.org) and restart your computer |
| Page won't load | Wait 10 seconds — servers may still be starting up |
| Port already in use | Close other apps using port 3000 or 8000 |
| Backend errors | Make sure your Anthropic API key is set (see below) |

### Setting your API key

The AI agents need an Anthropic API key to function. Create a file called `.env` in the `packages/api/` folder:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Without this key, document upload will work but agent processing will not run.
