import getopt
import glob
import json
import subprocess
import sys
import tempfile
import time
import urllib, urllib2

# options
DEBUG = False
RUN_NUMBER = 1
PHANTOMJS_PATH = 'phantomjs'
VERBOSE = False
PAGES_PER_BATCH = 1
STOP_ON_EMPTY = False

def usage():
  print "python driver.py -r <run> --debug --phantomjs-path=<path>"

try:
  opts, args = getopt.getopt(sys.argv[1:], "hr:dp:vb:s", ["help", "run=", "debug", "phantomjs-path=", "verbose", "batch=", "stop"])
except getopt.GetoptError, err:
  # print help information and exit:
  print str(err) # will print something like "option -a not recognized"
  usage()
  sys.exit(2)

for o, a in opts:
  if o in ("-v", "--verbose"):
    VERBOSE = True
  elif o in ("-h", "--help"):
    usage()
    sys.exit()
  elif o in ("-r", "--run"):
    RUN_NUMBER = int(a)
  elif o in ("-b", "--batch"):
    PAGES_PER_BATCH = int(a)
  elif o in ("-d", "--debug"):
    DEBUG = True
  elif o in ("-s", "--stop"):
    STOP_ON_EMPTY = True
  elif o in ("-p", "--phantomjs-path"):
    PHANTOMJS_PATH = a
  else:
    assert False, "unhandled option"

# dependant constants
TARGET_SERVER = "ldr.myvnc.com:8889" if DEBUG else "cs261.freewli.com"    
QUEUE_URL = "http://%s/cs261/queue_page/list/.json?run=%d&limit=%%d" % (TARGET_SERVER, RUN_NUMBER)

# Build JS file
out = tempfile.NamedTemporaryFile(suffix='.js')
for fn in glob.glob('modules/*.js'):
  f = open(fn, 'r')
  out.write(f.read())
  out.write('\n')

out.write(open('base.js', 'r').read())
out.flush()
print out.name

while True:
  f = urllib2.urlopen(QUEUE_URL % PAGES_PER_BATCH)
  data = json.loads(f.read())

  if len(data["message"]["pages"]) == 0:
    if STOP_ON_EMPTY:
      print "No more pages to run. Stopping execution..."
      break
    else:
      print "No more pages to run. Sleeping for 30 seconds..."
      time.sleep(30)
      continue

  print "%d page(s) to process..." % len(data["message"]["pages"])

  for target_page in data["message"]["pages"]:
    target_url = target_page["url"]
    print "Processing %s" % target_url

    # Run JS file
    phantom = subprocess.Popen([PHANTOMJS_PATH, '--load-images=no', out.name, target_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    phantom.wait()

    # Get HTTP headers
    header_data = {}
    h = urllib2.urlopen(target_url)

    for k, v in h.info().items():
      if k == "server":
        header_data["server_version"] = v
      if k == "x-powered-by":
        header_data["powered_by"] = v
        if v.startswith("PHP/"):
          header_data["php_version"] = v.replace("PHP/", '')

    success = False
    for line in phantom.stdout:
      if line.startswith("[[measurement]] "):
        line = line.replace("[[measurement]] ", "")
        data = json.loads(line)
        data['run'] = RUN_NUMBER
        data['page_id'] = target_page['id']
        data.update(header_data)
        f = urllib2.urlopen("http://%s/cs261/internet_page/add/" % TARGET_SERVER,
                            urllib.urlencode(data))
        # print f.read()
        # print urllib.urlencode(data)
        print data
        success = True
    if not success:
      print "Failed! Try re-running this command with xvfb-run if you're connectd via SSH."
      exit

# Delete temporary JS file
out.close()
