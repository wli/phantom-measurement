# coding=utf-8
import boto
import collections
import errno
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
TIMEOUT = 30

def usage():
  print "python driver.py -r <run> --debug --phantomjs-path=<path>"

def report_failure(**kwargs):
  try:
    if VERBOSE: print kwargs['reason']
    opener.open("http://%s/cs261/failed_page/add/" % TARGET_SERVER,
                urllib.urlencode(kwargs),
                timeout=TIMEOUT)
  except:
    print "Can't contact main server to report problems."


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
  #try:
  #  f = opener.open(QUEUE_URL % PAGES_PER_BATCH, timeout=TIMEOUT)
  #except:
  #  print "Could not contact main server. Sleeping for 30 seconds..."
  #  time.sleep(30)
  #  continue
  #r = f.read()
  #try:
  #  data = json.loads(r)
  #except:
  #  print r
  #  break

  #if data["message"] == "kill":
  #  print "Received kill command."
  #  exit()

  #if len(data["pages"]) == 0:
  #  if STOP_ON_EMPTY:
  #    print "No more pages to run. Stopping execution..."
  #    break
  #  else:
  #    print "No more pages to run. Sleeping for 30 seconds..."
  #    time.sleep(30)
  #    continue

  data = {'pages': [{'url': 'http://www.google.com/language_tools?hl=en', 'id': 1, 'run': 999999, 'depth': 0}]}

  print "%d page(s) to process..." % len(data["pages"])

  for target_page in data["pages"]:
    print "Processing %s" % target_page['url']

    output = tempfile.NamedTemporaryFile()

    # Clear the proxy log
    httpd.logs = []

    # Filter hashes from URLs
    request_url, fragment = urlparse.urldefrag(target_page['url'])
    if fragment and fragment[0] == '!':
      # Move fragment to request_url
      request_url += ('&' if '?' in request_url else '?') + '_escaped_fragment_=' + urllib.quote(fragment[1:])

    # Run JS file
    phantom = subprocess.Popen([PHANTOMJS_PATH, '--load-plugins=no', '--proxy=' + httpd_addr, js.name, request_url, output.name])#, stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)
    now = time.time()
    phantom_timed_out = False
    while True: # If not terminated:
      phantom.poll()
      if phantom.returncode is not None: break

      if (time.time() - now) > TIMEOUT:
        phantom.terminate()
        phantom_timed_out = True
        print "Killed PhantomJS for taking too much time."
        report_failure(url=target_page['url'], run=RUN_NUMBER, page_id=target_page['id'], reason='PhantomJS timeout')
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
      print data
    except ValueError:
      data = {}
      if not phantom_timed_out: failed = True

    # Extract desired header data
    url = data['url'] if 'url' in data else target_page['url']
    for connection in connection_log:
      if connection['request_uri'] == request_url:
        headers = connection['response_headers']
        break
    else:
      try:
        h = opener.open(request_url, timeout=TIMEOUT)
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
        report_failure(url=target_page['url'], run=RUN_NUMBER, page_id=target_page['id'], reason='header timeout\n' + e.read())

        print "Header timeout failed."
        continue # Move onto next page

    # Add headers to data
    data['headers'] = ['%s: %s' % (key.lower(), value) for key, value in headers]

    # Add transfer information to data
    transfers = collections.defaultdict(int)
    for connection in connection_log:
      transfers[connection['request_uri']] += connection['response_payload_size']
    data['transfers'] = transfers

    # Page row
    all_items = []
    page = sdb_domain.new_item('page-%d' % target_page['id'])
    page['run'] = RUN_NUMBER
    page['original_url'] = target_page['url'] # original url
    page['url'] = data['url'] if 'url' in data else target_page['url'] # final url
    page['page_id'] = target_page['id']
    page['depth'] = target_page['depth']
    all_items.append(page)
    
    # Rows for other PhantomJS data
    wanted_keys = ('cookies', 'frames', 'images', 'jquery', 'links', 'scripts', 'secureForm', 'stylesheets', 'connections', 'headers', 'transfers')
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
        row['page_id'] = page['page_id']
        for v in group:
          if v is None: break
          v = json.dumps(v)
          if len(v) > 1024: 
            report_failure(url=target_page['url'], run=RUN_NUMBER, page_id=target_page['id'], reason='Value too large: %s=%s' % (key, v))
          else: row.add_value(key, v)
        all_items.append(row)

    for item in all_items:
      try:
        if VERBOSE: 
          print item.name
          pprint.pprint(item)
        item.save()
      except boto.exception.SDBResponseError as e:
        print "SimpleDB Failure."
        report_failure(url=target_page['url'], run=RUN_NUMBER, page_id=target_page['id'], reason='SimpleDB Failure: ' + str(e))

    try:
      command_data = {
        'run': RUN_NUMBER,
        'url': target_page['url'],
        'page_id': target_page['id'],
        'depth': target_page['depth'],
        'links': data['links'] if 'links' in data else {}
      }
      for k,v in command_data.iteritems():
        command_data[k] = json.dumps(v)
      if VERBOSE: print command_data 
      f = opener.open("http://%s/cs261/internet_page/add/" % TARGET_SERVER,
                        urllib.urlencode(command_data),
                        timeout=TIMEOUT)
    except:
      pass

    if failed:
      print "Failed! Try re-running this command with xvfb-run if you're connectd via SSH."
      exit()
    
  break

# Delete temporary JS file
js.close()
