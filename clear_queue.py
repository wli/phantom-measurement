import sys, getopt, pika
from pika import BlockingConnection

DEBUG = False
RUN_NUMBER = 1

def usage():
  print "python clear_queue.py -r <run> --debug"

try:
  opts, args = getopt.getopt(sys.argv[1:], "hr:dv", ["help", "run=", "debug", "verbose"])
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
  elif o in ("-d", "--debug"):
    DEBUG = True
  else:
    assert False, "unhandled option"

# Connect to RabbitMQ
TARGET_RMQ_SERVER = "ldr.myvnc.com" if DEBUG else "noddy.cs.berkeley.edu"
parameters = pika.ConnectionParameters(TARGET_RMQ_SERVER)
rmq_connection = BlockingConnection(parameters)
rmq_channel = rmq_connection.channel()

rmq_channel.queue_declare(queue="run%d" % RUN_NUMBER, durable=True,
                          exclusive=False, auto_delete=False)

num_cleared = 0
def handle_delivery(channel, method_frame, header_frame, body):
  # Receive the data in 3 frames from RabbitMQ
  if VERBOSE:
    pika.log.info("Basic.Deliver %s delivery-tag %i: %s",
                  header_frame.content_type,
                  method_frame.delivery_tag,
                  body)
  rmq_channel.basic_ack(delivery_tag=method_frame.delivery_tag)
  num_cleared += 1
  print "Cleared %d messages" % (num_cleared)

# We're stuck looping here since this is a blocking adapter
rmq_channel.basic_consume(handle_delivery, queue='run%d' % RUN_NUMBER)
rmq_channel.start_consuming()
