# Skill: Python Data Scientist

## Overview
Use this skill when asked to analyze data, manipulate datasets, or generate charts using Python.

## Tools & Libraries
- Use `pandas` for data manipulation (CSV, JSON, SQL).
- Use `matplotlib.pyplot` or `seaborn` for plotting.
- Use `numpy` for numerical operations.

## Workflow
1. Ensure the required libraries are installed. If using the `execute_python` tool, pass `["pandas", "matplotlib"]` to the `dependencies` array.
2. When loading data, always handle potential missing files or encoding issues (`try/except` blocks).
3. If generating a chart, always save it to the disk (e.g., `plt.savefig("chart.png")`) instead of trying to display it interactively with `plt.show()`, as the agent runs headlessly.
4. When summarizing data, use `df.describe()` and `df.info()` to understand the structure before writing complex logic.

## Common Errors
- `FileNotFoundError`: Double-check the absolute path to the dataset.
- `ModuleNotFoundError`: Ensure you specified the dependency in the `execute_python` tool.