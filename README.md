# Trade Data Quality

A small Streamlit project exploring how trade data can be checked before it is used for reporting.

I built this as a learning exercise while preparing for interviews in banking data roles. It uses **fictional data** and is **not a Nordea application or a production reporting tool**.

## What it shows

- **Reporting overview:** Compare totals before and after data-quality checks.
- **Data checks & ownership:** See which records need attention and which team could investigate them.
- **Definitions & traceability:** Understand reporting rules and follow a trade through the checks.

The example data includes trades, instrument details and foreign-exchange rates. Python and SQL are used to identify repeated trade messages, handle cancelled trades, check missing information and prepare a cleaner reporting view.

The sidebar lets you change a sample scenario, such as adding a missing FX rate or a repeated trade message, and see how the results change.

## Tools

Python · SQL (SQLite) · pandas · Streamlit

## Run locally

1. Install Python.
2. Open a terminal in the project folder.
3. Install the requirements:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Start the app:

   ```bash
   python -m streamlit run app.py
   ```

## Files

- `app.py` — dashboard and user controls
- `pipeline.py` — SQL selection, validation and reporting calculations
- `data_generator.py` — fictional sample data
- `.streamlit/config.toml` — application colours and theme
- `tests/` — basic checks of the processing logic

## Important note
All records, amounts and example ownership suggestions are fictional. Differences between displayed totals illustrate reporting-data quality issues; they do **not** represent financial losses, actual exposures or official regulatory figures.


All records, amounts and example ownership suggestions are fictional. Differences between displayed totals illustrate reporting-data quality issues; they do **not** represent financial losses, actual exposures or official regulatory figures.

