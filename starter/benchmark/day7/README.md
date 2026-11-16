# Day 7 benchmark — UNICEF Viet Nam 2045 report

This is the question set and gold evidence for the 136-page UNICEF report
*Children at the Heart of Viet Nam's New Era*. It contains 20 answerable
questions (15 dev, 5 test) and four insufficient-evidence questions (2 dev,
2 test), meeting the Day 7 minimum. Answerable questions cover education,
health and nutrition, WASH, social protection, child protection, equity,
climate, and the conclusion.

## Files and source

- [`questions.json`](questions.json) contains only user questions, split, and
  any filter explicitly provided by the question. It deliberately contains no
  answerability labels or gold answers.
- [`gold.json`](gold.json) maps question IDs to expected answers and evidence.
  Do not pass this file, its excerpts, or derived labels to the agent.
- [`../../data/day7/manifest.yaml`](../../data/day7/manifest.yaml) records the
  source, page scope, extraction checks, and section metadata.
- PDF source:
  <https://www.unicef.org/vietnam/vi/media/19741/file/Final%20-%20Designed%20Viet%20Nam%202045%20Full%20Report-En.pdf.pdf>

The local source file expected by the manifest is
`starter/data/Final - Designed Viet Nam 2045 Full Report-En.pdf.pdf`. It is not
included in this benchmark package; obtain it from the source URL. Evidence
uses **1-based physical PDF pages**, so page references remain unambiguous even
where printed folios differ.

The complete PDF has 136 physical pages. The manifest counts 107 substantive
pages: PDF pages 9–14 and 16–114, plus the two substantive annex pages 134–135.
It excludes cover/title and front matter, references, and the contact page.
All counted pages contain extractable text. The PDF is UNICEF-hosted; no open
redistribution license was confirmed, so do not redistribute the full report
without checking permissions.

## Evaluation protocol

1. Use the same source snapshot, chunk index, embedding model, vector store,
   distance metric, and questions for all retrieval methods. Suggested
   comparison: A = fixed 700-character chunks with 100-character overlap;
   B = paragraph-aware chunks capped at 700 characters; C = B plus the
   `section` metadata filter only when the question supplies a filter.
   Record any different parameters, versions, context construction, costs,
   errors, and timing.
2. Select/tune with dev only. Freeze the method and selection rule before
   running test. An initial A/B/C retrieval and context run was performed on
   2026-11-16 and its test results are saved below; the test split is now
   exposed, not blind. Any further tuning based on these results requires a
   fresh test set for independent evaluation.
3. Calculate Hit@1, Evidence Hit@3, and Context Evidence Rate only over
   answerable questions: denominators are 15 dev and 5 test. Evidence must
   support the requested facts, including all requested comparison values or
   conditions. For insufficient-evidence queries, do not count a retrieval miss
   as an accuracy error; assess whether the agent abstains.
4. Evaluate the final context actually sent to the model, not just the first
   retrieval result. Report its budget and unit (preferably tokens), selection
   method, candidate count, and whether evidence is complete. A multi-evidence
   answer is complete only if the context contains support for every requested
   part.
5. On test, manually review at least five answerable questions and both
   insufficient-evidence questions for the baseline and selected method.
   Label context 0/1/2 and answer grounding 0/1/2 as defined in `BENCHMARK 2.md`.
   Check every citation against the quoted context and source; record labels,
   reasons, tool calls, time, cost, and errors separately.
6. The four abstention cases are intentionally close to report topics. Their
   full-document search notes are in the gold file. A keyword search or a
   missing top-k hit alone does not establish that evidence is absent; manually
   confirm each case before final scoring.

Questions with an explicit section reference include a `filter` in the public
question file. Apply it only in the filter-aware method, before retrieval, and
never infer filters from gold source/page labels.

## Ingest and index

The Day 7 ingester stores prefixed strategies `day7_A`, `day7_B`, and `day7_C`
in the existing `day6_chunks` table, leaving Day 6 strategy rows untouched.
It embeds A and B once; C reuses B's chunks and vectors. After indexing it
checks the stored row counts and writes timing/configuration metadata to
`starter/results/day7/ingest_metadata.json`.

With Docker PostgreSQL + pgvector running and embedding settings in
`starter/.env`, run from the repository root:

```bash
docker compose -f starter/docker-compose.yml -p day6_student_starter up -d --wait
(cd starter && .venv/bin/python -m scripts.run_day7_ingestion)
```

The command sends document chunks to the configured embedding provider and may
incur API charges. It does not run retrieval metrics or the answer-generation
agent.

## Run retrieval and context evaluation

After indexing, run the same 24 public questions against `day7_A/B/C`:

```bash
(cd starter && .venv/bin/python -m scripts.run_day7_retrieval_context)
```

The runner embeds each question once, reuses it across strategies, returns
top-3, and saves:

- `starter/results/day7/retrieval_context_traces.json`: rankings, context sent
  by the current chatbot formatter, automatic evidence checks, and timings.
- `starter/results/day7/retrieval_context_summary.json`: Hit@1, Evidence Hit@3,
  and Context Evidence Rate (`n/N`) for answerable dev and test questions.
- `starter/results/day7/retrieval_context_run.json`: corpus/index hashes,
  model, context construction, and runtime metadata.

Initial run results (20 answerable questions; 15 dev / 5 test):

| Strategy | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate |
|---|---|---:|---:|---:|
| A | Dev | 9/15 | 12/15 | 12/15 |
| A | Test* | 4/5 | 5/5 | 5/5 |
| B | Dev | 6/15 | 9/15 | 9/15 |
| B | Test* | 2/5 | 2/5 | 2/5 |
| C | Dev | 8/15 | 10/15 | 10/15 |
| C | Test* | 2/5 | 2/5 | 2/5 |

*\*The test set has now been run and inspected; these figures are descriptive,
not a blind final comparison.*

The final context consists of all three retrieved chunks with page/section
labels, matching `RetrievalChatbot._context`; no reranking, truncation, or chat
model call is made. Context budget is therefore top-3 chunks and reported in
characters rather than tokens. Insufficient-evidence questions are included in
the traces but excluded from retrieval and context accuracy denominators. This
runner does not evaluate answer grounding, citation validity, or abstention;
those require an agent run and human review.

## Validate source evidence

From the repository root, run:

```bash
(cd starter && .venv/bin/python -m scripts.validate_day7_benchmark)
```

The validator checks split counts, question/gold separation, source page ranges,
PDF checksum/page count, and that each answerable quote appears on its cited
PDF page. The insufficient-evidence judgments still require human review.
