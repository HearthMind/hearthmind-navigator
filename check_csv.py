import csv

rows = list(csv.DictReader(open('/home/hyperion/hearthmind/data/raw/sam_assistance_listings_20260207.csv', encoding='latin-1')))
real = [r for r in rows if r['Program Title'] not in ('Not Applicable', '') and r['Objectives (050)'] not in ('Not Applicable', '')]

print(f'Total rows: {len(rows)}')
print(f'Real programs: {len(real)}')
print('Columns:', list(rows[0].keys())[:10])

r = real[0]
print('\nSample:')
print(' Title:', r['Program Title'][:70])
print(' Agency:', r['Federal Agency (030)'][:70])
print(' Type:', r['Types of Assistance (060)'][:70])
print(' Eligibility:', r['Applicant Eligibility (081)'][:120])
print(' Objectives:', r['Objectives (050)'][:120])

# Check agency spread
from collections import Counter
agencies = Counter(r['Federal Agency (030)'] for r in real)
print('\nTop agencies:')
for agency, count in agencies.most_common(8):
    print(f'  {count:4d}  {agency[:60]}')
