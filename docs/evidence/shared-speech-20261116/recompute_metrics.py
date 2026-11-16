"""Recompute the frozen error counts without publishing corpus transcripts."""
from pathlib import Path
import argparse,json,re,unicodedata

def units(text):return re.findall(r"[\u3400-\u9fff]|[a-z0-9]+(?:'[a-z0-9]+)*",unicodedata.normalize('NFKC',text).lower())
def distance(a,b):
 row=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  next_row=[i]
  for j,y in enumerate(b,1):next_row.append(min(next_row[-1]+1,row[j]+1,row[j-1]+(x!=y)))
  row=next_row
 return row[-1]
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--private-corpus',type=Path,required=True);args=parser.parse_args()
 frozen=json.loads((Path(__file__).parent/'public-trial-results.json').read_text(encoding='utf-8'))
 checked=0
 for result in frozen['results']:
  rows=json.loads((args.private_corpus/(result['model']+'-transcripts-private.json')).read_text(encoding='utf-8'));mapping={r['id']:r for r in result['cases']}
  for r in rows:
   old=mapping[r['id']];assert len(units(r['reference']))==old['units'];assert distance(units(r['reference']),units(r['recognized']))==old['edits'];checked+=1
 print(json.dumps({'passed':True,'recording_model_pairs':checked,'transcripts_published':False}))
