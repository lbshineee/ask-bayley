# Ask Bayley

An SFBU student guide for deadlines, policies, and campus support. This hackathon starter uses curated notes from public SFBU sources.

## Run on a Mac or Linux laptop

Open a terminal in the extracted `ask-bayley` folder. Use Python 3.12 to match the DGX if available.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). Type “When do classes start in Spring 2027?” or “What is the Summer 2027 add/drop deadline?” and press Enter. For a term-independent question, try “Where do I get Canvas help?” Laptop preview works with the included source notes and does not require an API key.

## Put the starter in GitHub

Create an empty private repository called `ask-bayley` under `lbshineee`. Then run the following from the project folder on the laptop.

```bash
git init -b main
git add .
git commit -m "Initialize Ask Bayley"
git remote add origin https://github.com/lbshineee/ask-bayley.git
git push -u origin main
```

If you already initialized the folder or added the remote, inspect `git status` and `git remote -v` before repeating those steps.

## Run on the DGX

Run these commands on the DGX after pushing the starter.

```bash
git clone https://github.com/lbshineee/ask-bayley.git
cd ask-bayley
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For live drafting, enter your student Open WebUI API key at the hidden Bash prompt.

```bash
export BAYLEY_WEBUI_URL=http://localhost:8080
export BAYLEY_MODEL=qwen3:32b
read -r -s -p 'Student Open WebUI API key: ' BAYLEY_WEBUI_API_KEY
printf '\n'
export BAYLEY_WEBUI_API_KEY
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in the DGX browser. Start without the API key for the same local preview as on the laptop. With the key set, the app submits the question and matching public source notes to the configured Open WebUI endpoint and shows the model draft above the notes.

After pushing changes from the laptop, run `git pull --ff-only` inside the DGX checkout. Install requirements again if they changed and restart Streamlit. Keep credentials in the terminal session.

## Source data and scope

- `data/sources.json` holds the seven public URLs reviewed by the project owner.
- `data/entries.json` holds the starter notes. Check the dates and applicability against the linked pages before the demo. Calendar notes cover standard semesters.
- Retrieval uses keyword matching. Include the term and year in questions about dates. The sidebar lists reference links, including pages beyond the starter notes. There is no automatic document ingestion or embedding index in this starter.

## Minimal mascot chat update

The home page has one question field and the original Bayley the Bayhawk image underneath. Submit a message to switch to a chat with Bayley as the assistant avatar. The transition happens on submission, not while typing. History lasts for the browser session; New conversation is in the sidebar. Each question is retrieved independently, so include the term/year again when relevant. This UI update does not expand the knowledge base or add document ingestion.

To apply this archive to an existing checkout, merge its files into your laptop's ask-bayley folder, keeping your existing .git and .venv folders. The assets/bayley.png file is required. Review git diff, commit the updated files and push. On the DGX, stop Streamlit with Ctrl+C, run git pull --ff-only and restart with .venv/bin/python -m streamlit run app.py. Configure the API key in that terminal for model drafting, as described above. No API keys are included in this archive.
