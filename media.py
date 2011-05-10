import urllib2
import json
import base64
import re
import sys
from statlib import stats
from collections import defaultdict

req = urllib2.Request("http://noddy.cs.berkeley.edu:5984/run3/_design/pages/_view/%s_length?group=true" % sys.argv[1])
base64string = base64.encodestring('%s:%s' % ('measurement', 'g0b3ars'))[:-1]
req.add_header("Authorization", "Basic %s" % base64string)

r = urllib2.urlopen(req)

d = json.loads(r.read())
buckets = {"0": 0, "1-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-50": 0, "50+": 0}
vals = []

for row in d["rows"]:
    vals += [row['key']] * row['value']
    if row['key'] == 0:
        buckets["0"] += row['value']
    elif row['key'] <= 10:
        buckets["1-10"] += row['value']
    elif row['key'] <= 20:
        buckets["11-20"] += row['value']
    elif row['key'] <= 30:
        buckets["21-30"] += row['value']
    elif row['key'] <= 40:
        buckets["31-40"] += row['value']
    elif row['key'] <= 50:
        buckets["41-50"] += row['value']
    else:
        buckets["50+"] += row['value']

for t, n in sorted(buckets.items()):
  print "%s\t%d" % (t, n)

print "mean:   %.2f" % stats.mean(vals)
print "median: %.2f" % stats.median(vals)

f = open('/home/wli/scratch/%s.json' % sys.argv[1], 'w')
f.write(json.dumps(buckets))
f.close()
