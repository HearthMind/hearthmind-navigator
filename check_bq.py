from google.cloud import bigquery
c = bigquery.Client(project='spheric-duality-466022-p6')
q = """
SELECT 
  category,
  COUNT(*) as cnt,
  COUNT(DISTINCT agency) as agencies
FROM navigator_benefits.programs 
GROUP BY category 
ORDER BY cnt DESC 
LIMIT 15
"""
print("=== BigQuery programs by category ===")
for row in c.query(q).result():
    print(f"  {row.cnt:4d}  {row.category or 'null':<20}  {row.agencies} agencies")

q2 = "SELECT COUNT(*) as total FROM navigator_benefits.programs"
for row in c.query(q2).result():
    print(f"\nTotal programs: {row.total}")

q3 = "SELECT name, agency, category FROM navigator_benefits.programs LIMIT 3"
print("\nSample records:")
for row in c.query(q3).result():
    print(f"  {row.name[:60]} | {row.agency[:30]} | {row.category}")
