# coding=utf-8
import collections
import couchdb
import errno
import getopt
import glob
import itertools
import json
import os
import pika
import pprint
import random
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib
import urllib2
import urlparse

import proxy
from pika.adapters import BlockingConnection

pika.log.setup(color=True)

#signal.signal(signal.SIGINT, lambda a, b: sys.exit())

# options
DEBUG = False
RUN_NUMBER = 1
PHANTOMJS_PATH = 'phantomjs'
VERBOSE = False
PAGES_PER_BATCH = 1
STOP_ON_EMPTY = False
TIMEOUT = 60

def usage():
  print "python driver.py -r <run> --debug --phantomjs-path=<path>"

def async(func):
  threading.Thread(target=func).start()

def report_failure(url, run, reason):
  global cdb_server
  try:
    fdb = cdb_server["run%d-failures" % RUN_NUMBER]
  except:
    fdb = cdb_server.create("run%d-failures" % RUN_NUMBER)
  fdb[url] = {'url': url, 'run': run, 'reason': reason}

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

# Build JS file
js = tempfile.NamedTemporaryFile(suffix='.js')
for fn in glob.glob('modules/*.js'):
  f = open(fn, 'r')
  js.write(f.read())
  js.write('\n')

js.write(open('base.js', 'r').read())
js.flush()

# build URL opener
opener = urllib2.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.24 (KHTML, like Gecko) Chrome/11.0.696.50 Safari/534.24'), ('Accept', 'application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5'), ('Accept-Language', 'en-US,en;q=0.8'), ('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.3')]

# Start the proxy
httpd = proxy.start_proxy()
httpd_addr = '%s:%d' % httpd.server_address

# connect to CouchDB
TARGET_CDB_SERVER = "http://ldr.myvnc.com:5984" if DEBUG else "http://noddy.cs.berkeley.edu:5984"
cdb_server = couchdb.client.Server(url=TARGET_CDB_SERVER)
cdb_server.resource.credentials = ('measurement', 'g0b3ars')
try:
  cdb = cdb_server["run%d" % RUN_NUMBER]
except:
  cdb = cdb_server.create("run%d" % RUN_NUMBER)

# Connect to RabbitMQ
TARGET_RMQ_SERVER = "ldr.myvnc.com" if DEBUG else "noddy.cs.berkeley.edu"
parameters = pika.ConnectionParameters(TARGET_RMQ_SERVER)
rmq_connection = BlockingConnection(parameters)
rmq_channel = rmq_connection.channel()

rmq_channel.queue_declare(queue="run%d" % RUN_NUMBER, durable=True,
                          exclusive=False, auto_delete=False)

def handle_delivery(channel, method_frame, header_frame, body):
  # Receive the data in 3 frames from RabbitMQ
  if VERBOSE:
    pika.log.info("Basic.Deliver %s delivery-tag %i: %s",
                  header_frame.content_type,
                  method_frame.delivery_tag,
                  body)

  try:
    target_page = json.loads(body)
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
        report_failure(url=target_page['url'], run=RUN_NUMBER, reason='PhantomJS timeout')
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
    for connection in connection_log:
      if connection['request_uri'] == request_url:
        headers = connection['response_headers']
        break
    else:
      try:
        h = opener.open(request_url, timeout=TIMEOUT)
        headers = h.info().items()
      except urllib2.URLError as e:
        report_failure(url=target_page['url'], run=RUN_NUMBER, reason='header timeout\n' + (e.read() if 'read' in dir(e) else ''))

        print "Header timeout failed."
        return # Move onto next page
        #continue

    # Add headers to data
    data['headers'] = ['%s: %s' % (key.lower(), value) for key, value in headers]

    # Add transfer information to data
    transfers = collections.defaultdict(int)
    for connection in connection_log:
      transfers[connection['request_uri']] += connection['response_payload_size']
    data['transfers'] = transfers

    # Page row
    page = {}
    page['run'] = RUN_NUMBER
    page['original_url'] = target_page['url'] # original url
    page['url'] = data['url'] if 'url' in data else target_page['url'] # final url
    #page['page_id'] = target_page['id']
    page['depth'] = target_page['depth']

    page.update(data)

    if VERBOSE:
      print "Saving %s" % page['original_url']
      pprint(page)
    try:
      cdb[page['original_url']] = page
    except:
      print "CouchDB Failure, possible key collision"

    if target_page['depth'] > 0 and 'links' in page:
      links = sorted(page['links'].items(), key=lambda x: x[1], reverse=True)
      scale_factor = 1
      for i in range(target_page['fanout']):
        if len(links) > 0:
          r = random.random() * scale_factor
          for url, weight in links:
            r -= weight
            if r <= 0:
              command_data = {
                'run': RUN_NUMBER,
                'url': url,
                'fanout': target_page['fanout'],
                'depth': target_page['depth'] - 1
                }
              if VERBOSE:
                print "Adding page %s" % url
              rmq_channel.basic_publish(exchange='',
                                        routing_key="run%d" % RUN_NUMBER,
                                        body=json.dumps(command_data),
                                        properties=pika.BasicProperties(
                  content_type="text/plain",
                  delivery_mode=1))
              scale_factor -= weight
              links.remove((url, weight))
              break

    if VERBOSE:
      print 'Acking...',
    rmq_channel.basic_ack(delivery_tag=method_frame.delivery_tag)
    if VERBOSE:
      print 'Done! Waiting for another response...'
    if failed:
      print "Failed! Try re-running this command with xvfb-run if you're connectd via SSH."
      exit()
  except:
    print "Could not parse RabbitMQ response."
    raise

# We're stuck looping here since this is a blocking adapter
rmq_channel.basic_consume(handle_delivery, queue='run%d' % RUN_NUMBER)
rmq_channel.start_consuming()

rmq_connection.close()

# Delete temporary JS file
js.close()
