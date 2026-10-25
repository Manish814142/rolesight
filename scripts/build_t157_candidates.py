"""Generate candidate companies for T157 according to criteria.

Criteria:
- A technology or product company with an engineering team in India.
- About 200 to 5,000 employees.
- Either total funding of US$25M or more with a round in the last 4 years (2021-2025),
  or profitable and established (8+ years, or listed).
- Not a staffing or recruitment agency; no IT-services body shop.

Sources (public pages only):
- Wikipedia Indian Unicorns (valuation $1B+, tech/product)
- Elevation Capital portfolio (growth / venture / tech)
- Peak XV Partners portfolio (growth / venture / tech)
- Matrix Partners India / Z47 portfolio
- Nexus Venture Partners India portfolio
- Entrackr top growth funding deals (2024 & 2025)
"""

import csv
import json
import os
import re
import urllib.request

from bs4 import BeautifulSoup


def clean_name(n: str) -> str:
    n = re.sub(r'\[.*?\]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


EXCLUDE_NAMES = {
    # Physical retail / food & beverage chains / physical clinics & hospitals
    'cafe coffee day', 'chaayos', 'california burrito', 'chai point', 'w for women',
    'centre for sight', 'cloudnine', 'suburban diagnostics', 'sks microfinance',
    'abcoffee', 'blue tokai', 'wow! momo', 'the whole truth', 'open secret',
    'foxtale', 'damensch', 'bare anatomy', 'country delight', 'bliss club',

    # Southeast Asia / foreign entities without India engineering team
    'goto', 'carousell', 'bibit', 'pluang', 'kumu', 'shajgoj', '10 minute school',
    'alodokter', 'kopi kenangan', 'chope', 'ninja van', 'finaccel', 'kudo',
    'circles.life', 'circles life', 'tabby', 'alaan', 'airalo', 'appier',

    # Heavy manufacturing / batteries / pharma contract research / pure telecom infra
    'amara raja group', 'aragen life sciences', 'gvk biosciences', 'aricent',
    'aptus housing finance', 'five star', 'five-star', 'muthoot finance',
    'centum electronics',

    # IT services / body shops / staffing agencies / massive MNCs
    'akurateco', 'tcs', 'wipro', 'infosys', 'cognizant', 'hcl', 'hcl tech',
    'tech mahindra', 'genpact', 'l&t technology services', 'mphasis', 'hexaware',
    'teamlease', 'quess', 'quess corp', 'adecco', 'randstad', 'manpowergroup',
    'amazon', 'google', 'microsoft', 'apple', 'meta', 'flipkart', 'reliance'
}


def main():
    candidates = {}

    # 1. Wikipedia Indian Unicorns
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_unicorn_startup_companies'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            soup = BeautifulSoup(r.read().decode('utf-8'), 'html.parser')
        for table in soup.find_all('table', {'class': 'wikitable'}):
            for tr in table.find_all('tr'):
                text = tr.get_text()
                if 'India' in text:
                    cols = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if cols:
                        name = clean_name(cols[0])
                        if name and name.lower() not in EXCLUDE_NAMES and name not in ['Company', 'India', 'Total']:
                            val = re.sub(r'\[.*?\]', '', cols[1]).strip() if len(cols) > 1 else '1.0+'
                            val = val.replace('$', '')
                            date_str = re.sub(r'\[.*?\]', '', cols[2]).strip() if len(cols) > 2 else ''
                            candidates[name.lower()] = {
                                'name': name,
                                'source_url': url,
                                'funding_evidence': f'Unicorn (Valuation: ${val}B, {date_str})',
                                'size_evidence': '',
                                'measured_or_inferred': 'measured funding (Wikipedia)'
                            }
    except Exception as e:
        print('Wikipedia fetch error:', e)

    # 2. Elevation Capital Portfolio
    try:
        url = 'https://www.elevationcapital.com/portfolio'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        data = json.loads(soup.find('script', id='__NEXT_DATA__').string)

        def find_portfolios(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == 'portfolios' and isinstance(v, list):
                        return v
                    res = find_portfolios(v)
                    if res:
                        return res
            elif isinstance(d, list):
                for x in d:
                    res = find_portfolios(x)
                    if res:
                        return res
            return None

        ports = find_portfolios(data) or []
        for p in ports:
            name = clean_name(p.get('title', ''))
            stage = p.get('stageType', {}).get('title', '') if isinstance(p.get('stageType'), dict) else ''
            slug = p.get('slug', '')
            if name and name.lower() not in EXCLUDE_NAMES and name.lower() not in candidates:
                # Keep tech / consumer tech / fintech / enterprise AI
                candidates[name.lower()] = {
                    'name': name,
                    'source_url': f'https://www.elevationcapital.com/portfolio/{slug}' if slug else url,
                    'funding_evidence': f'Elevation Capital portfolio ({stage or "Venture/Growth"})',
                    'size_evidence': '',
                    'measured_or_inferred': 'measured portfolio/stage'
                }
    except Exception as e:
        print('Elevation fetch error:', e)

    # 3. Peak XV Partners Portfolio
    try:
        url = 'https://www.peakxv.com/our-companies'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('div', class_='com-header_inline-item')
        for item in items:
            lines = [s.strip() for s in item.get_text(separator='\n').splitlines() if s.strip()]
            if not lines:
                continue
            name = clean_name(lines[0])
            stage = ''
            year = ''
            if 'Stage' in lines:
                idx = lines.index('Stage')
                if idx + 1 < len(lines):
                    stage = lines[idx + 1]
            if 'First Partnered' in lines:
                idx = lines.index('First Partnered')
                if idx + 1 < len(lines):
                    year = lines[idx + 1]
            a = item.find('a', href=True)
            link = f'https://www.peakxv.com{a["href"]}' if a else url
            if not name or 'stealth' in name.lower() or name == 'No items found.' or name.lower() in EXCLUDE_NAMES:
                continue
            # Filter for mid-size / growth / venture / tech
            if stage in ['Growth', 'Venture', 'IPO', 'Series A'] or year in ['2021', '2022', '2023', '2024', '2025', '2026']:
                if name.lower() not in candidates:
                    candidates[name.lower()] = {
                        'name': name,
                        'source_url': link,
                        'funding_evidence': f'Peak XV ({stage}, partnered {year})',
                        'size_evidence': '',
                        'measured_or_inferred': 'measured portfolio/stage'
                    }
    except Exception as e:
        print('Peak XV fetch error:', e)

    # 4. Matrix Partners India / Z47 Portfolio
    try:
        url = 'https://www.z47.com/portfolio'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            soup = BeautifulSoup(r.read().decode('utf-8'), 'html.parser')
        for a in soup.find_all('a', href=re.compile(r'^/portfolio/[a-zA-Z0-9\-]+$')):
            slug = a['href'].replace('/portfolio/', '')
            name = slug.replace('-', ' ').title()
            if name.lower() not in EXCLUDE_NAMES and name.lower() not in candidates:
                candidates[name.lower()] = {
                    'name': name,
                    'source_url': f'https://www.z47.com/portfolio/{slug}',
                    'funding_evidence': 'Matrix Partners / Z47 portfolio',
                    'size_evidence': '',
                    'measured_or_inferred': 'measured portfolio'
                }
    except Exception as e:
        print('Z47 fetch error:', e)

    # 5. Nexus Venture Partners India Portfolio
    try:
        url = 'https://www.nexusvp.com/in/companies'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            soup = BeautifulSoup(r.read().decode('utf-8'), 'html.parser')
        for a in soup.find_all('a', href=re.compile(r'/companies/[a-zA-Z0-9\-]+')):
            slug = a['href'].split('/')[-1]
            name = slug.replace('-', ' ').title()
            desc = a.get_text(strip=True)
            if name.lower() not in EXCLUDE_NAMES and name.lower() not in candidates:
                candidates[name.lower()] = {
                    'name': name,
                    'source_url': f'https://www.nexusvp.com/in/companies/{slug}',
                    'funding_evidence': f'Nexus VP India portfolio ({desc[:40]})',
                    'size_evidence': '',
                    'measured_or_inferred': 'measured portfolio'
                }
    except Exception as e:
        print('Nexus VP fetch error:', e)

    # 6. Entrackr Top Growth Funding Deals (2024 & 2025)
    entrackr_deals = [
        ('Zepto', '$1.35B (2024) / $450M (2025)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('Impetus Technologies', '$350M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('Innovaccer', '$275M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('Uniphore', '$260M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('Zolve', '$251M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('Porter', '$200M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('PharmEasy', '$216M (2024) / $193M (2025)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('MoEngage', '$180M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('Atlan', '$105M (2024)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('Pocket FM', '$103M (2024)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('Shadowfax', '$100M (2024)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('SEDEMAC', '$100M (2024)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('Lenskart', '$200M (2024)', 'https://entrackr.com/2024/12/exclusive-indian-startups-scooped-up-14-4-bn-funding-in-2024/'),
        ('Eruditus', '$150M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
        ('Weaver Services', '$170M (2025)', 'https://entrackr.com/2025/12/indian-startups-raised-13-bn-in-2025-ipo-hit-record-high/'),
    ]
    for n, f, u in entrackr_deals:
        if n.lower() not in EXCLUDE_NAMES and n.lower() not in candidates:
            candidates[n.lower()] = {
                'name': n,
                'source_url': u,
                'funding_evidence': f'Growth round: {f}',
                'size_evidence': '',
                'measured_or_inferred': 'measured funding (Entrackr)'
            }

    rows = list(candidates.values())
    print(f'Total candidates compiled: {len(rows)}')

    os.makedirs('data', exist_ok=True)
    tsv_path = 'data/t157_candidates.tsv'
    with open(tsv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['name', 'source_url', 'funding_evidence', 'size_evidence', 'measured_or_inferred'])
        for r in sorted(rows, key=lambda x: x['name'].lower()):
            writer.writerow([r['name'], r['source_url'], r['funding_evidence'], r['size_evidence'], r['measured_or_inferred']])

    print(f'Successfully wrote {len(rows)} candidates to {tsv_path}')


if __name__ == '__main__':
    main()
