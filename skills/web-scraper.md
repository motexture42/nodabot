# Skill: Web Scraper & Data Extractor

## Overview
Use this skill when asked to extract data from websites, scrape content, or automate browser interactions for data gathering.

## Tools
- For simple, static HTML pages: Use `requests` and `BeautifulSoup`.
- For complex, dynamic, or JavaScript-heavy pages: Use the built-in `browser_controller` tool or write a Playwright Python script.

## Workflow
1. Check `robots.txt` before scraping a site to ensure compliance.
2. When using `requests`, always supply a realistic `User-Agent` header to prevent being immediately blocked by basic anti-bot systems.
3. If scraping a list of items, extract the data into a structured format (like a list of dictionaries) and save it to a JSON or CSV file immediately.
4. **Resilience**: Websites change. Wrap your extraction logic (e.g., `soup.find()`) in try-except blocks and handle cases where the element is `None`.

## Rate Limiting
Do not hit a server with hundreds of requests a second. If writing a scraping loop, include `time.sleep(1)` to act like a polite bot.