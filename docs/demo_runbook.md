# Demo Runbook

## Pre-Demo Checklist
- [ ] Refresh virtualenv (`module load Python/3.11.5-GCCcore-13.2.0 && source .venv/bin/activate`).
- [ ] Run `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --enrichr-libraries Reactome_2022 --use-mageck false` to pre-generate artifacts.
- [ ] Launch Dash (`python app.py`) two minutes before presentation.
- [ ] Open artifacts directory and confirm latest run exists.
- [ ] Disable LLM narratives unless OpenAI quota confirmed.

## Live Script (3 Minutes)
1. **Intro (20s)** – "CRISPR-studio automates pooled CRISPR screen analysis end-to-end." Show Upload tab with files pre-loaded.
2. **Configuration (20s)** – Highlight metadata summary, FDR threshold, mention optional advanced settings.
3. **Run Analysis (10s)** – Trigger Run Analysis (background job) but mention results precomputed.
4. **Results Tour (60s)** – Volcano plot, summary cards, click BRCA2 to open modal. Emphasise quick access to annotations + QC badges.
5. **QC & Pathways (40s)** – Flip to QC tab (replicate correlation badge), then Pathways bubble chart showing DNA damage pathways.
6. **Report (20s)** – Download HTML report, note shareable artifact.
7. **Conclusion (10s)** – Mention CLI + Docker support, invite questions.

## Backup Plan
- If MAGeCK fails (demo dataset too small), reference RRA fallback and highlight warning banner.
- Keep pre-rendered screenshots (see docs/marketing_assets.md storyboard) on standby.
- For UI hiccups, showcase CLI output + report HTML in browser.

## Slide Outline
1. Problem statement: "CRISPR screens produce millions of reads, analysis is bottlenecked."
2. Solution overview: architecture diagram showing upload → pipeline → insights.
3. Results snapshot: volcano plot + QC badges.
4. Impact metrics: runtime, hit overlap, pilot lab testimonials.
5. Call-to-action: beta cohort, admissions showcase.
