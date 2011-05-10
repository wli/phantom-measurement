import urllib2
import json
import base64

req = urllib2.Request("http://noddy.cs.berkeley.edu:5984/run3/_design/pages/_view/jquery_versions?group=true")
base64string = base64.encodestring('%s:%s' % ('measurement', 'g0b3ars'))[:-1]
req.add_header("Authorization", "Basic %s" % base64string)

r = urllib2.urlopen(req)

d = json.loads(r.read())
versions = {}
for row in d["rows"]:
  versions[row['key']] = row['value']

types = {"1.0": 0, "1.1": 0, "1.2": 0, "1.3": 0, "1.4": 0, "1.5": 0, "1.6": 0, "no_jquery": 0, "other": 0}

for s, n in versions.items():
  for t in types.keys():
    if s.lower().startswith(t):
      types[t] += n
      break
  else:
    types["other"] += n

for t, n in types.items():
  print "%s.x\t%d" % (t, n)

f = open('/home/wli/scratch/jquery.json', 'w')
f.write(json.dumps(versions))
f.close()
