# PRISM Benchmark Results

Benchmark results for [PRISM](https://github.com/Nabin-16/PRISM-Reliability-test-), a tool that tests how reliably local LLMs answer the same question when the prompt is worded differently.

Instead of just checking if a model gets an answer right, PRISM asks: *does it still get it right when you say the same thing five different ways?* That consistency score is what we track here.

---

## What's in here

```
results/
├── index.json          # quick lookup — one entry per approved model run
├── summary.csv         # everything in one table, easy to open in Excel or pandas
├── summary.json        # same thing but JSON
└── models/
    ├── llama3.2_3b.json
    ├── gemma3_4b.json
    ├── mistral_7b.json
    └── phi4_mini.json
```

Each model file has the full per-dataset breakdown. The `summary` files pull the headline numbers together for easy comparison.

---

## How results get here

Results don't land here automatically. The pipeline goes:

1. Someone runs the PRISM desktop app and submits their benchmark
2. It goes into a private review queue (Supabase)
3. A maintainer looks it over and approves it
4. An automated sync job picks up the approved results and updates this repo

So everything here has been manually reviewed at least once before publishing.

---

## The numbers

All runs use the same setup so results are comparable across models:

- **Datasets:** ARC-Challenge (grade-school science) and SciQ (crowdsourced science exams)
- **Sample size:** 200 questions per dataset, same seed every time (`2026`)
- **Prompt variants:** 5 different phrasings of each question
- **Models tested so far:** Llama 3.2 3B, Gemma 3 4B, Mistral 7B, Phi-4 Mini

### Key metrics

| Metric | What it means |
|--------|--------------|
| Accuracy | How often the model got the right answer |
| Answer Recovery | If it got question wrong on the first try, did it recover on other phrasings? |
| Prompt Sensitivity | How much the model's answer changed based on how the question was asked |
| Agreement | How often all 5 prompt variants gave the same answer |

Low sensitivity + high agreement = a model that answers based on what you're asking, not how you happened to phrase it.

---

## Models tested

| Model | Parameters | Accuracy (ARC) | Accuracy (SciQ) |
|-------|-----------|----------------|-----------------|
| Llama 3.2 | 3B | see results/ | see results/ |
| Gemma 3 | 4B | see results/ | see results/ |
| Mistral | 7B | see results/ | see results/ |
| Phi-4 Mini | 3.8B | see results/ | see results/ |

(Numbers update when new approved runs come in — check `results/summary.csv` for the latest.)

---

## Running it yourself

The desktop app is at [Nabin-16/PRISM-Reliability-test-](https://github.com/Nabin-16/PRISM-Reliability-test-). It handles everything — Ollama, the prompt variations, scoring, and submission. You just need the models pulled locally.

Results you run yourself won't appear in this repo automatically (they go through the review queue first), but the app will show you your own local results immediately after the run.
