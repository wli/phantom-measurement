import getopt
import glob
import json
import subprocess
import sys
import tempfile
import time
import os
import json
import pprint
import urllib, urllib2

# options
DEBUG = False
RUN_NUMBER = 1
PHANTOMJS_PATH = 'phantomjs'
VERBOSE = False
PAGES_PER_BATCH = 1
STOP_ON_EMPTY = False
TIMEOUT = 15

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
js = tempfile.NamedTemporaryFile(suffix='.js')
for fn in glob.glob('modules/*.js'):
  f = open(fn, 'r')
  js.write(f.read())
  js.write('\n')

js.write(open('base.js', 'r').read())
js.flush()

opener = urllib2.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.24 (KHTML, like Gecko) Chrome/11.0.696.50 Safari/534.24'), ('Accept', 'application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5'), ('Accept-Language', 'en-US,en;q=0.8'), ('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.3')]

while True:
  f = urllib2.urlopen(QUEUE_URL % PAGES_PER_BATCH)
  data = json.loads(f.read())

  if data["status"] == "kill":
    print "Received kill command."
    exit

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

    output = tempfile.NamedTemporaryFile()

    # Run JS file
    phantom = subprocess.Popen([PHANTOMJS_PATH, js.name, target_url, output.name], stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)
    now = time.time()
    phantom_timed_out = False
    while True: # If not terminated:
      phantom.poll()
      if phantom.returncode is not None: break

      if (time.time() - now) > TIMEOUT:
        phantom.terminate()
        phantom_timed_out = True
        print "Killed PhantomJS for taking too much time."
        break
      time.sleep(0.5)
    
    # Get HTTP headers
    header_data = {}
    try:
      h = opener.open(target_url, timeout=TIMEOUT)

      for k, v in h.info().items():
        if k == "server":
          header_data["server_version"] = v
        if k == "x-powered-by":
          header_data["powered_by"] = v
          if v.startswith("PHP/"):
            header_data["php_version"] = v.replace("PHP/", '')
      header_data["headers"] = h.info().items()
    except:
      opener.open("http://%s/cs261/failed_page/add/" % TARGET_SERVER,
                  urllib.urlencode({'url': target_url, 'run': RUN_NUMBER}),
                  timeout=TIMEOUT)
      pass

    failed = False
    output.seek(0)

    try:
      data = json.loads(output.read())
    except ValueError:
      data = {}
      if not phantom_timed_out: failed = True

    data['run'] = RUN_NUMBER
    data['page_id'] = target_page['id']
    data['depth'] = target_page['depth']

    data.update(header_data)
    for key in data.iterkeys():
      data[key] = json.dumps(data[key])
    try:
      f = opener.open("http://%s/cs261/internet_page/add/" % TARGET_SERVER,
                      urllib.urlencode(data),
                      timeout=TIMEOUT)
      pprint.pprint(data)
    #except urllib2.URLError as e:
    #  #x = open('/var/www/error.html', 'w')
    #  #x.write(e.read())
    #  #x.close()
    #  #print e.read()
    except:
      failed = True

    if failed:
      print "Failed! Try re-running this command with xvfb-run if you're connectd via SSH."
      exit

# Delete temporary JS file
js.close()
