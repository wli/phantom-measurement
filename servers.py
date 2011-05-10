import urllib2
import json
import base64
import re
from collections import defaultdict

req = urllib2.Request("http://noddy.cs.berkeley.edu:5984/run3/_design/pages/_view/server_versions?group=true")
base64string = base64.encodestring('%s:%s' % ('measurement', 'g0b3ars'))[:-1]
req.add_header("Authorization", "Basic %s" % base64string)

r = urllib2.urlopen(req)

d = json.loads(r.read())
servers = {}
php_versions = defaultdict(int)
PHP_RE = re.compile(r"PHP/([0-9.]+)")
for row in d["rows"]:
  servers[row['key']] = row['value']
  match = PHP_RE.search(row['key'])
  if match:
      php_versions[match.group(1)] += row['value']

types = {"apache": 0, "nginx": 0, "gws": 0, "microsoft-iis": 0, "gse": 0, "ibm_http_server": 0, "other": 0}

for s, n in servers.items():
  for t in types.keys():
    if s.lower().startswith(t):
      types[t] += n
      break
  else:
    types["other"] += n

for t, n in sorted(types.items()):
  print "%s\t%d" % (t, n)

for t, n in sorted(php_versions.items()):
  print "%s\t%d" % (t, n)

f = open('/home/wli/scratch/servers.json', 'w')
f.write(json.dumps(servers))
f.close()
