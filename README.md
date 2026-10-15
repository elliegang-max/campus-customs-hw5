# hw5

Scaffold for the hw5 assignment. The brief has not been added yet — the layout
below follows the conventions used in `hw3/` and `hw4/`.

## Repository layout

```
hw5/
├── AI_prompts.md       # log of the prompts used to build this
├── requirements.txt    # Python deps
├── .env.example        # environment template (copy to .env)
├── .gitignore
├── README.md
├── prompts/            # system / task prompts
├── data/               # data pack (not committed)
└── output/             # write-ups and generated artefacts
```

## Setup

```bash
cp .env.example .env    # then fill in PORTKEY_API_KEY and PORTKEY_BASE_URL
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
