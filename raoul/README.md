# Raoul — NYC Rules Assistant

> **"Hey Raoul, What's the Rule?"**
>
> A plain-language chat interface that helps New Yorkers understand the rules of their city — in any language.

---

## What Raoul Does

Raoul uses Claude (Anthropic's AI) to answer questions about NYC rules in plain, accessible language. It's built for everyday New Yorkers, not lawyers. Key features:

- **Real-time parking lookups** — queries the official NYC DOT parking sign database (updated daily) to tell you what the signs say on any specific block
- **ASP suspension checking** — knows whether alternate side parking is suspended today
- **12 languages** — English, Spanish, Chinese (Simplified & Traditional), Russian, Bengali, Haitian Creole, Korean, Arabic, Polish, Urdu, French
- **Cites sources** — every answer links to the specific rule or agency
- **Mobile-first design** — inspired by access.nyc.gov
- **Deploys free on Vercel** — static frontend + Python serverless backend

---

## Project Structure

```
raoul/
├── public/
│   └── index.html          # Mobile-first chat interface (no build step)
├── api/
│   ├── index.py            # FastAPI serverless handler (Vercel function)
│   ├── _prompts.py         # Raoul's system prompt
│   └── _tools.py           # NYC Open Data integrations
├── backend/                # Standalone backend (for local dev without Vercel)
│   ├── main.py
│   ├── prompts.py
│   └── tools.py
├── vercel.json             # Vercel routing and function config
├── requirements.txt        # Python dependencies (used by Vercel)
├── .env.example
├── .gitignore
└── README.md
```

---

## Deploy to Vercel (Recommended)

### Prerequisites

- A free [Vercel account](https://vercel.com/signup)
- A free [GitHub account](https://github.com/signup)
- An [Anthropic API key](https://console.anthropic.com)
- [Git](https://git-scm.com/downloads) installed on your computer

### Step 1: Create a GitHub Repository

Open Terminal (Mac) or Command Prompt (Windows) and run:

```bash
# Navigate to the raoul folder
cd path/to/raoul

# Initialize a git repo
git init

# Add all files
git add .

# Create the first commit
git commit -m "Initial commit: Raoul NYC Rules Assistant"
```

Then go to [github.com/new](https://github.com/new) in your browser:
1. Name the repo `raoul` (or whatever you prefer)
2. Leave it as **Public** or set to **Private**
3. Do NOT check "Add a README" (we already have one)
4. Click **Create repository**

GitHub will show you setup commands. Run the ones under "push an existing repository":

```bash
git remote add origin https://github.com/YOUR_USERNAME/raoul.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Vercel

1. Go to [vercel.com/new](https://vercel.com/new)
2. Click **Import** next to your `raoul` repository
3. Vercel will auto-detect the project settings from `vercel.json` — you don't need to change anything
4. Before clicking Deploy, expand **Environment Variables** and add:

   | Name | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | `sk-ant-...` (your Anthropic API key) |

5. Click **Deploy**

Vercel will build and deploy in about 30 seconds. You'll get a URL like `https://raoul-xxxxx.vercel.app`.

### Step 3: Open Raoul

Visit your Vercel URL. You should see the "Hey Raoul, What's the Rule?" splash page. Click an example chip or type a question — Raoul will answer.

### Updating After Changes

After making changes to any file:

```bash
git add .
git commit -m "Description of change"
git push
```

Vercel auto-deploys on every push to `main`.

---

## Local Development (Alternative)

If you prefer to run locally instead of deploying to Vercel:

```bash
# Install dependencies
cd raoul
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Start the backend
cd backend
uvicorn main:app --reload --port 8000

# Then open public/index.html in your browser
# Note: update API_URL in public/index.html to 'http://localhost:8000'
```

---

## Data Sources

| Source | What it provides | Update frequency |
|---|---|---|
| [NYC DOT Parking Signs](https://data.cityofnewyork.us/Transportation/Parking-Regulation-Locations-and-Signs/xswq-wnv9) | Block-level parking sign text | Daily |
| [NYC DOT ASP page](https://www.nyc.gov/html/dot/html/motorist/alternate-side-parking.shtml) | Today's suspension status | Real-time |
| Built-in holiday calendar | ASP suspension fallback | Static (update annually) |
| Claude's training knowledge | All other NYC rules (RCNY, Admin Code) | Model cutoff |

---

## Roadmap

### Phase 2 — Knowledge Base (RAG)
Scrape all ~6,000 RCNY sections from American Legal Publishing, embed them, and add a `search_rcny(query)` tool for precise rule retrieval.

### Phase 3 — More NYC Open Data integrations
311 service categories, OATH fine schedules, DOB permit lookup, zoning data, HPD complaints.

### Phase 4 — Production features
Rate limiting, conversation memory, feedback collection, PWA installability, automated RCNY update pipeline.

---

## Credits

- **[Rules of the City of New York](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCrules/0-0-0-1)** via American Legal Publishing
- **[NYC DOT Parking Sign Database](https://data.cityofnewyork.us/Transportation/Parking-Regulation-Locations-and-Signs/xswq-wnv9)** via NYC Open Data
- **Design**: Inspired by [ACCESS NYC](https://access.nyc.gov)
- **Font**: [Noto Sans](https://fonts.google.com/noto) by Google
- **AI**: [Claude](https://anthropic.com) by Anthropic

---

## Disclaimer

Raoul provides general information about NYC rules, not legal advice. Information may be incomplete or out of date. For legal matters, consult a licensed attorney. For city services, call 311. For emergencies, call 911. This tool is not affiliated with or endorsed by the City of New York.
