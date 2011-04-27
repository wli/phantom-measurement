# Copyright (c) 2001 SUZUKI Hisao 
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions: 
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software. 
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# http://www.oki-osk.jp/esc/python/proxy/

__doc__ = """Tiny HTTP Proxy.

This module implements GET, HEAD, POST, PUT and DELETE methods
on BaseHTTPServer, and behaves as an HTTP proxy.  The CONNECT
method is also implemented experimentally, but has not been
tested yet.

Any help will be greatly appreciated.		SUZUKI Hisao
"""

__version__ = "0.2.1"

import BaseHTTPServer, select, socket, SocketServer, urlparse
import cStringIO as StringIO
import json
import threading

class HTTPLoggedRequest(object):
  def __init__(self, destination):
    self.destination = destination
    self.headers = None
    self.payload_size = 0

    self.headers_remaining = True
    self.header_data = StringIO.StringIO()

  def observe(self, data):
    if hasattr(self, 'headers_remaining'): 
      # Look for \r\n\r\n, or the end of headers
      headers, sep, payload = data.partition('\r\n\r\n')
      self.header_data.write(headers)
      if sep != '':
        self.header_data.write(sep)
        self.payload_size += len(payload)
        self.headers = self.header_data.getvalue()

        del self.headers_remaining
        del self.header_data
    else:
      self.payload_size += len(data)

class TunnelLoggedRequest(object):
  def __init__(self, destination):
    self.destination = destination
    self.received_bytes = 0

  def observe(self, data):
    self.received_bytes += len(data)
  
class ProxyHandler (BaseHTTPServer.BaseHTTPRequestHandler):
  __base = BaseHTTPServer.BaseHTTPRequestHandler
  __base_handle = __base.handle

  server_version = "TinyHTTPProxy/" + __version__
  rbufsize = 0            # self.rfile Be unbuffered

  def _connect_to(self, netloc, soc):
    i = netloc.find(':')
    if i >= 0:
      host_port = netloc[:i], int(netloc[i+1:])
    else:
      host_port = netloc, 80
#    print "\t" "connect to %s:%d" % host_port
    try: soc.connect(host_port)
    except socket.error, arg:
      try: msg = arg[1]
      except: msg = arg
      self.send_error(504, msg)
      return 0
    return 1

  def do_CONNECT(self):
    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logger = TunnelLoggedRequest(self.path)
    try:
      if self._connect_to(self.path, soc):
#        self.log_request(200)
        self.wfile.write(self.protocol_version +
                 " 200 Connection established\r\n")
        self.wfile.write("Proxy-agent: %s\r\n" % self.version_string())
        self.wfile.write("\r\n")
        self._read_write(soc, logger, 300)
    finally:
#      print "\t" "bye"
      soc.close()
      self.request.close()
      self.server.log(logger)

  def do_GET(self):
    (scm, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
    logger = HTTPLoggedRequest(self.path)
    if scm != 'http' or fragment or not netloc:
      self.send_error(400, "bad url %s" % self.path)
      return
    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      if self._connect_to(netloc, soc):
#        self.log_request()
        soc.send("%s %s %s\r\n" % (
          self.command,
          urlparse.urlunparse(('', '', path, params, query, '')),
          self.request_version))
        self.headers['Connection'] = 'close'
        del self.headers['Proxy-Connection']
        for key_val in self.headers.items():
          soc.send("%s: %s\r\n" % key_val)
        soc.send("\r\n")
        self._read_write(soc, logger)
    finally:
      #print "\t" "bye"
      soc.close()
      self.request.close()
      self.server.log(logger)

  def _read_write(self, soc, logger, max_idling=20):
    iw = [self.request, soc]
    ow = []
    count = 0
    while 1:
      count += 1
      (ins, _, exs) = select.select(iw, ow, iw, 3)
      if exs: break
      if ins:
        for i in ins:
          data = i.recv(8192)
          if data:
            if i is soc:
              self.request.send(data)
              logger.observe(data)
            else:
              soc.send(data)
            count = 0
      #else:
      #  print "\t" "idle", count
      if count == max_idling: break

  do_HEAD = do_GET
  do_POST = do_GET
  do_PUT  = do_GET
  do_DELETE=do_GET

class ThreadingHTTPServer (SocketServer.ThreadingMixIn,
               BaseHTTPServer.HTTPServer):
  def __init__(self, *args, **kwargs):
    BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
    self.logs = []

  def log(self, logger):
    self.logs.append(logger.__dict__)

def start_proxy():
  httpd = None
  port = 8123
  while True:
    try:
      httpd = ThreadingHTTPServer(('localhost', port), ProxyHandler)
      break
    except socket.error as e:
      if hasattr(e, 'errno') and e.errno == errno.EADDRINUSE:
        port += 1
        continue
      else: raise

  t = threading.Thread(target=httpd.serve_forever, args=(60,))
  t.daemon = True
  t.start()
  return httpd

if __name__ == '__main__':
  import signal, sys
  server_address = ('localhost', 8000)
  httpd = ThreadingHTTPServer(server_address, ProxyHandler)
  signal.signal(signal.SIGINT, lambda a, b: sys.exit())
  httpd.serve_forever()
