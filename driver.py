# coding=utf-8
import boto
import getopt
import glob
import itertools
import json
import os
import pprint
import signal
import subprocess
import sys
import tempfile
import time
import urllib
import urllib2
import urlparse

import proxy

#signal.signal(signal.SIGINT, lambda a, b: sys.exit())

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

# open up a connection to SimpleDB
sdb = boto.connect_sdb('1KP2TM5CMYJAWJ8R5V02', 'f0CVp8g8Vbc49sHr7LVIIB1El2Y990XUro7QgVsd')
try:
  sdb_domain = sdb.get_domain('measurement', validate=True)
except boto.exception.SDBResponseError:
  print "Error: SimpleDB domain 'measurement' does not exist. Creating..."
  sdb_domain = sdb.create_domain('measurement')
  exit()

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

# Start the proxy
httpd = proxy.start_proxy()
httpd_addr = '%s:%d' % httpd.server_address

while True:
  try:
    f = opener.open(QUEUE_URL % PAGES_PER_BATCH, timeout=TIMEOUT)
  except:
    print "Could not contact main server. Sleeping for 30 seconds..."
    time.sleep(30)
    continue
  r = f.read()
  try:
    data = json.loads(r)
  except:
    print r
    break

  if data["message"] == "kill":
    print "Received kill command."
    exit()

  if len(data["pages"]) == 0:
    if STOP_ON_EMPTY:
      print "No more pages to run. Stopping execution..."
      break
    else:
      print "No more pages to run. Sleeping for 30 seconds..."
      time.sleep(30)
      continue

  print "%d page(s) to process..." % len(data["pages"])

  for target_page in data["pages"]:
    target_url = target_page["url"]
    print "Processing %s" % target_url

    output = tempfile.NamedTemporaryFile()

    # Clear the proxy log
    httpd.logs = []

    # Run JS file
    phantom = subprocess.Popen([PHANTOMJS_PATH, '--load-plugins=yes', '--proxy=' + httpd_addr, js.name, target_url, output.name], stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)
    now = time.time()
    phantom_timed_out = False
    while True: # If not terminated:
      phantom.poll()
      if phantom.returncode is not None: break

      if (time.time() - now) > TIMEOUT:
        phantom.terminate()
        phantom_timed_out = True
        print "Killed PhantomJS for taking too much time."
        try:
          opener.open("http://%s/cs261/failed_page/add/" % TARGET_SERVER,
                      urllib.urlencode({'url': target_url, 'run': RUN_NUMBER, 'page_id': target_page['id'], 'reason': 'PhantomJS timeout'}),
                      timeout=TIMEOUT)
        except:
          print "Could not contact main server."
          pass
        break
      time.sleep(0.5)
    
    # Get proxy log
    connection_log = httpd.logs

    # TODO: Get local and SQL storage
    # src/third_party/WebKit/Source/WebCore/page/SecurityOrigin.cpp
    # http://codesearch.google.com/codesearch/p#OAMlx_jo-ck/src/third_party/WebKit/Source/WebCore/page/SecurityOrigin.cpp&l=463

    # TODO: Get Flash LSOs


    failed = False
    output.seek(0)

    try:
      data = json.loads(output.read())
    except ValueError:
      data = {}
      if not phantom_timed_out: failed = True

    # Extract desired header data
    url = data['url'] if 'url' in data else target_page['url']
    defragged_url = urlparse.urldefrag(url)[0]
    for connection in connection_log:
      if connection['request_uri'] == defragged_url:
        headers = connection['response_headers']
        break
    else:
      try:
        h = opener.open(defragged_url, timeout=TIMEOUT)
        headers = h.info().items()
        #for k, v in h.info().items():
        #  if k == "server":
        #    header_data["server_version"] = v
        #  if k == "x-powered-by":
        #    header_data["powered_by"] = v
        #    if v.startswith("PHP/"):
        #      header_data["php_version"] = v.replace("PHP/", '')
        #header_data["headers"] = h.info().items()
      except urllib2.URLError as e:
        try:
          opener.open("http://%s/cs261/failed_page/add/" % TARGET_SERVER,
                      urllib.urlencode({'url': target_url, 'run': RUN_NUMBER, 'page_id': target_page['id'], 'reason': 'header timeout\n' + e.read()}),
                      timeout=TIMEOUT)
        except:
          print "Could not contact main server."

        print "Header timeout failed."
        continue # Move onto next page
    headers = ['%s: %s' % (key.lower(), value) for key, value in headers]

    all_items = []
    
    # Page row
    page = sdb_domain.new_item('page-%d' % target_page['id'])
    page['run'] = RUN_NUMBER
    page['original_url'] = target_page['url'] # original url
    page['url'] = data['url'] if 'url' in data else target_page['url'] # final url
    page['page_id'] = target_page['id']
    page['depth'] = target_page['depth']
    all_items.append(page)
    
    # Rows for headers
    header_rows = []
    for num, header_group in enumerate(itertools.izip_longest(*([iter(headers)] * 250))):
      header_row = sdb_domain.new_item('header-%d-%d' % (num, target_page['id']))
      header_row['run'] = page['run']
      header_row['url'] = page['url']
      header_row['page_id'] = page['page_id']
      for header in header_group:
        if header is None: break
        v = json.dumps(header)
        if len(v) > 1024: errors.write('%s=%s\n' % ('header', v))
        else: header_row.add_value('header', v)

      all_items.append(header_row)

    # Rows for connections
    # TODO

    # Rows for other PhantomJS data
    wanted_keys = ('cookies', 'frames', 'images', 'jquery', 'links', 'scripts', 'secureForm', 'stylesheets')
    for key in wanted_keys:
      try: value = data[key]
      except: continue
      # Is it a list?
      if isinstance(value, (list, tuple)):
        pair_values = value

      # Is it a dictionary?
      elif isinstance(value, dict):
        pair_values = value.items()

      # Is it something else?
      else: pair_values = [value]

      for num, group in enumerate(itertools.izip_longest(*([iter(pair_values)] * 250))):
        row = sdb_domain.new_item('%s-%d-%d' % (key, num, target_page['id']))
        row['run'] = page['run']
        row['url'] = page['url']
        row['page_id'] = page['page_id']
        for v in pair_values:
          v = json.dumps(v)
          if len(v) > 1024: errors.write('%s=%s\n' % (key, v))
          else: row.add_value(key, v)
        all_items.append(row)

    try:
      for item in all_items:
#        print item
        item.save()

      command_data = {
        'run': RUN_NUMBER,
        'url': target_page['url'],
        'page_id': target_page['id'],
        'depth': target_page['depth'],
        'links': data['links'],
        }
      for k,v in command_data.items():
        command_data[k] = json.dumps(v)

      f = opener.open("http://%s/cs261/internet_page/add/" % TARGET_SERVER,
                      urllib.urlencode(command_data),
                      timeout=TIMEOUT)
      if VERBOSE:
        pprint.pprint(data)
    except:
      raise

    if failed:
      print "Failed! Try re-running this command with xvfb-run if you're connectd via SSH."
      exit()

# Delete temporary JS file
js.close()
