# Beta Feedback Plan

## Recruitment
- Leverage pilot labs identified in `docs/go_to_market.md` (target three labs).
- Offer complimentary analysis + onboarding session in exchange for structured feedback.
- Schedule 30-minute retrospective after each lab’s first real dataset.

## Feedback Form
- **Usability**: rate ease of upload, clarity of dashboards, report usefulness.
- **Accuracy**: compare CRISPR-studio hits/QC with lab’s expectations (free-form comments + checkboxes).
- **Performance**: capture runtime perception and dataset size.
- **Wishlist**: features requested, blockers to adoption, integrations needed.
- Host the form in Google Forms or Qualtrics; export CSV into `analytics/feedback.csv`.

## Triage Process
- Tag feedback as `bug`, `enhancement`, or `education`.
- Review weekly; update `docs/roadmap.md` with accepted enhancements.
- Log actionable items as GitHub issues (label by theme: UI, Analysis, Deployment).

## Success Criteria
- ≥3 labs complete full workflow and submit feedback.
- 90% of respondents express confidence in QC metrics.
- <5 critical bugs reported during beta period.
- At least one testimonial highlighting time savings or clarity of results.
