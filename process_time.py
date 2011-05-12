import urllib2
import json
import base64
import re
import sys
from statlib import stats
from collections import defaultdict

req = urllib2.Request("http://noddy.cs.berkeley.edu:5984/run4/_design/pages/_view/process_time?group=true")
base64string = base64.encodestring('%s:%s' % ('measurement', 'g0b3ars'))[:-1]
req.add_header("Authorization", "Basic %s" % base64string)

r = urllib2.urlopen(req)

d = json.loads(r.read())
buckets = {"0": 0, "1-5": 0, "6-10": 0, "11-15": 0, "16-20": 0, "21-25": 0, "26-30": 0, "31-35": 0, "36-40": 0, "41-45": 0, "46-50": 0, "51-55": 0, "56-60": 0, "61+": 0}
vals = []

for row in d["rows"]:
    vals += [row['key']] * row['value']
    if row['key'] == 0:
        buckets["0"] += row['value']
    elif row['key'] <= 5:
        buckets["1-5"] += row['value']
    elif row['key'] <= 10:
        buckets["6-10"] += row['value']
    elif row['key'] <= 15:
        buckets["11-15"] += row['value']
    elif row['key'] <= 20:
        buckets["16-20"] += row['value']
    elif row['key'] <= 25:
        buckets["21-25"] += row['value']
    elif row['key'] <= 30:
        buckets["26-30"] += row['value']
    elif row['key'] <= 35:
        buckets["31-35"] += row['value']
    elif row['key'] <= 40:
        buckets["36-40"] += row['value']
    elif row['key'] <= 45:
        buckets["41-45"] += row['value']
    elif row['key'] <= 50:
        buckets["46-50"] += row['value']
    elif row['key'] <= 55:
        buckets["51-55"] += row['value']
    elif row['key'] <= 60:
        buckets["56-60"] += row['value']
    else:
        buckets["61+"] += row['value']

for t, n in sorted(buckets.items()):
  print "%s\t%d" % (t, n)

print "mean:   %.2f" % max(vals)
print "mean:   %.2f" % stats.mean(vals)
print "median: %.2f" % stats.median(vals)

f = open('/home/wli/scratch/process_time.json', 'w')
f.write(json.dumps(buckets))
f.close()
