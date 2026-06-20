# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **documentation-only repository** — it contains a single `README.md` that serves as a public guide titled "How to share data with a statistician." There is no source code, build system, test suite, or package manager configuration.

## Content Structure

The entire content lives in `README.md` and covers four deliverables a collaborator should provide to a statistician:

1. **Raw data** — unmodified source data in its original form
2. **Tidy data set** — cleaned data following Hadley Wickham's tidy data principles (one variable per column, one observation per row, one table per variable kind)
3. **Code book** — describes each variable, its units, summary choices, and study design
4. **Instruction list/script** — reproducible recipe (preferably a script in R or Python) to go from raw → tidy data

## Editing Conventions

- The document is written in standard Markdown (GitHub-flavored)
- Missing values should always be coded as `NA`
- Categorical/ordinal variables should be stored as descriptive text strings, not numeric codes
- Censored data gets coded `NA` plus a companion boolean column named `VariableNameCensored`
- All information must be encoded as exportable text — no color/formatting-based encoding
