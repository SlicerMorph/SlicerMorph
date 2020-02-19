import os
from http.server import HTTPServer as BaseHTTPServer, SimpleHTTPRequestHandler

class WebViewMeshHTTPServer(BaseHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, ext_dir_path = '', ext_prefix = ''):
        super().__init__(server_address, RequestHandlerClass)
        self.ext_dir_path = ext_dir_path
        self.ext_prefix = ext_prefix

    def finish_request(self, request, client_address):
        """Finish one request by instantiating RequestHandlerClass."""
        self.RequestHandlerClass(request, client_address, self, ext_dir_path = self.ext_dir_path, ext_prefix = self.ext_prefix)

class WebViewMeshRequestHandler(SimpleHTTPRequestHandler):
  def __init__(self, *args, ext_dir_path = '', ext_prefix = ''):
    self.ext_dir_path = ext_dir_path
    self.ext_prefix = ext_prefix
    super().__init__(*args)

  def translate_path(self, path):
    if self.ext_prefix and self.path.startswith(self.ext_prefix):
      return self.ext_dir_path + path[len(self.ext_prefix):]
    else:
      base_path = os.path.dirname(os.path.abspath(__file__))
      return base_path + path

def serve_viewer(mesh_path, port = 8000):
    httpd = WebViewMeshHTTPServer(("", port),  WebViewMeshRequestHandler, ext_dir_path = mesh_path, ext_prefix='/mesh')
    httpd.serve_forever()

if __name__ == '__main__':
    serve_viewer(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mesh'))