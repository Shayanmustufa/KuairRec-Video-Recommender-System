# KuairRec Video Recommender System

A 15-day implementation of an explainable KuaiRec short-video recommender system.

## Stack

- Go backend
- Next.js frontend
- Python offline training
- PostgreSQL
- Docker Compose

## Status

Syed's complete Days 1–15 WBS is implemented and has passed the final audit,
including the frozen evaluation, failure analysis, evidence-backed report, and
checksum archive. See the
[final report](./docs/FINAL_REPORT.md), [data card](./docs/DATA_CARD.md), and
[offline pipeline instructions](./model/README.md). Abdul's backend/frontend
deliverables remain separate work.

## Project planning

- [Project plan](./plan.md)
- [Implementation phases](./phases.md)
- [KuaiRec data card](./docs/DATA_CARD.md)
- [Final model report](./docs/FINAL_REPORT.md)
- [Failure analysis](./docs/FAILURE_ANALYSIS.md)
- [Syed WBS final audit](./docs/SYED_WBS_AUDIT.md)
- [Final results appendix](./docs/RESULTS_APPENDIX.md)
- [Offline data pipeline](./model/README.md)

## Structure

- `backend/` - Go API and ranking services
- `frontend/` - Next.js web application
- `model/` - Data processing, training, and evaluation
- `docs/` - Architecture, reports, and data documentation
- `scripts/` - Development and automation scripts
- `data/` - Dataset placeholders and generated artifacts
