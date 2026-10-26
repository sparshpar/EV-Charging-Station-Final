import re
import sys

with open('frontend/mobile.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Balanced check
scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
for s_idx, s in enumerate(scripts):
    curly = s.count('{') - s.count('}')
    paren = s.count('(') - s.count(')')
    square = s.count('[') - s.count(']')
    assert curly == 0, f'script {s_idx} unbalanced curly: {curly}'
    assert paren == 0, f'script {s_idx} unbalanced paren: {paren}'
    assert square == 0, f'script {s_idx} unbalanced square: {square}'
print('[PASS] Balanced braces, brackets and parentheses in mobile.html!')

# 2. Check every document.getElementById('...') exists in HTML
ids_referenced = set(re.findall(r'document\.getElementById\(["\'](.*?)["\']\)', content))
all_html_ids = set(re.findall(r'id=["\'](.*?)["\']', content))

missing = [target_id for target_id in ids_referenced if target_id not in all_html_ids]

if missing:
    print('Missing IDs in HTML:', missing)
    sys.exit(1)
else:
    print(f'[PASS] All {len(ids_referenced)} getElementById targets exist in HTML!')
