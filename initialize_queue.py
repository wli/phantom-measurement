import csv
import getopt
import json
import os
import pika
import sys

from pika.adapters import BlockingConnection

RUN_NUMBER = None
FANOUT = None
DEPTH = None
NUM_SITES = None
DEBUG = False
OFFSET = 0

def usage():
  print "python initialize_queue.py -r <run> -n <num_sites> -f <fanout> -d <depth> -o <offset> --debug"

try:
  opts, args = getopt.getopt(sys.argv[1:], "hr:n:f:d:vo:", ["help", "run=", "num=", "fanout=", "depth=", "verbose", "debug", "offset="])
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
  elif o in ("-f", "--fanout"):
    FANOUT = int(a)
  elif o in ("-n", "--num"):
    NUM_SITES = int(a)
  elif o in ("-d", "--depth"):
    DEPTH = int(a)
  elif o in ("--debug"):
    DEBUG = True
  elif o in ("-o", "--offset"):
    OFFSET = int(a)
  else:
    assert False, "unhandled option"

if RUN_NUMBER is None:
    print "Run number (-r) must be specified"
if FANOUT is None:
    print "Fanout (-f) must be specified"
if DEPTH is None:
    print "Depth (-d) must be specified"
if NUM_SITES is None:
    print "Num sites (-n) must be specified"
if None in [RUN_NUMBER, FANOUT, DEPTH, NUM_SITES]:
    exit()

# Connect to RabbitMQ
TARGET_RMQ_SERVER = "ldr.myvnc.com" if DEBUG else "noddy.cs.berkeley.edu"
parameters = pika.ConnectionParameters(TARGET_RMQ_SERVER)
rmq_connection = BlockingConnection(parameters)
rmq_channel = rmq_connection.channel()

rmq_channel.queue_declare(queue="pages", durable=True,
                          exclusive=False, auto_delete=False)

reader = csv.reader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'top-1m.csv'), 'rb'))

n = 1
for row in reader:
    if n < OFFSET:
      n += 1
      continue
    url = "http://%s" % row[1]
    command_data = {
        'run': RUN_NUMBER,
        'url': url,
        'fanout': FANOUT,
        'depth': DEPTH
        }
    print "[%2d] Adding page %s..." % (n, url),
    rmq_channel.basic_publish(exchange='',
                              routing_key="run%d" % RUN_NUMBER,
                              body=json.dumps(command_data),
                              properties=pika.BasicProperties(
            content_type="text/plain",
            delivery_mode=1))
    print "Delivered"
    n += 1
    if n > NUM_SITES + OFFSET:
        break

rmq_connection.close()
