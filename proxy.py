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
import errno
import json
import threading
import time

class HTTPLoggedRequest(object):
  def __init__(self, method, destination):
    self.method = method
    self.request_uri = destination
    self.status = None
    self.response_headers = []
    self.unparsed_response_header_lines = []

    self.response_payload_size = 0
    self.request_payload_size = 0

    self.response_headers_remaining = True
    self.response_header_data = ''
    
    self.start_time = time.time()

  def observe_from_server(self, data):
    if hasattr(self, 'response_headers_remaining'): 
      # Look for \r\n\r\n, or the end of headers
      self.response_header_data += data
      headers, sep, payload = self.response_header_data.partition('\r\n\r\n')
      if sep != '':
        self.response_payload_size += len(payload)
#        self.response_header_data.seek(0)

        lines = iter(headers.split('\r\n'))
        self.status = lines.next().strip()
        
        for line in lines:
          try:
            name, value = line.split(':', 1)
            self.response_headers.append((name, value.strip()))
          except:
            self.unparsed_response_header_lines.append(line)

        del self.response_headers_remaining
        del self.response_header_data
        if not self.unparsed_response_header_lines: del self.unparsed_response_header_lines
    else:
      self.response_payload_size += len(data)
  
  def observe_from_client(self, data):
    self.request_payload_size += len(data)

  def add_request_headers(self, headers):
    self.request_headers = headers.items()

  def finished(self):
    self.elapsed_time = time.time() - self.start_time
    del self.start_time

class TunnelLoggedRequest(object):
  def __init__(self, destination):
    self.method = 'CONNECT'
    self.request_uri = destination

    self.response_payload_size = 0
    self.request_payload_size = 0

    self.start_time = time.time()

  def observe_from_client(self, data):
    self.request_payload_size += len(data)

  def observe_from_server(self, data):
    self.response_payload_size += len(data)

  def finished(self):
    self.elapsed_time = time.time() - self.start_time
    del self.start_time
  
def supply_http_logger(func, method):
  return lambda self: func(self, HTTPLoggedRequest(method, self.path))

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
      logger.finished()
      self.server.log(logger)

  def _respond(self, logger):
    (scm, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
    if scm != 'http' or fragment or not netloc:
      self.send_error(400, "bad url %s" % self.path)
      return

    logger.add_request_headers(self.headers)

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
      logger.finished()
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
          try:
            data = i.recv(8192)
          except:
            data = ''

          if data:
            if i is soc:
              self.request.send(data)
              logger.observe_from_server(data)
            else:
              soc.send(data)
              logger.observe_from_client(data)
            count = 0
      #else:
      #  print "\t" "idle", count
      if count == max_idling: break

  do_GET    = supply_http_logger(_respond, 'GET')
  do_HEAD   = supply_http_logger(_respond, 'HEAD')
  do_POST   = supply_http_logger(_respond, 'POST')
  do_PUT    = supply_http_logger(_respond, 'PUT')
  do_DELETE = supply_http_logger(_respond, 'DELETE')

class ThreadingHTTPServer (SocketServer.ThreadingMixIn,
               BaseHTTPServer.HTTPServer):
  def __init__(self, *args, **kwargs):
    BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
    self.logs = []

  def log(self, logger):
    # print logger.__dict__
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
