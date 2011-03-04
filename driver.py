import glob
import subprocess
import tempfile
import json
import urllib, urllib2

RUN = 1
PHANTOMJS_PATH = 'phantomjs'

# Build JS file
out = tempfile.NamedTemporaryFile(suffix='.js')
for fn in glob.glob('modules/*.js'):
  f = open(fn, 'r')
  out.write(f.read())
  out.write('\n')

out.write(open('base.js', 'r').read())
out.flush()
print out.name


# Run JS file
phantom = subprocess.Popen([PHANTOMJS_PATH, '--load-images=no', out.name, 'http://www.jquery.com'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
phantom.wait()

for line in phantom.stdout:
  if line.startswith("[[measurement]] "):
    line = line.replace("[[measurement]] ", "")
    data = json.loads(line)
    data['run'] = RUN
    f = urllib2.urlopen("http://cs261.freewli.com/cs261/internet_page/add/",
                    urllib.urlencode(data))
    # print f.read()
    # print urllib.urlencode(data)
    print data

# Process output

# Delete temporary JS file
out.close()
