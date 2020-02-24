from http.server import HTTPServer as BaseHTTPServer, SimpleHTTPRequestHandler
server_address = ("", 8000)

external_mesh_dir = '/Users/jmw110/data/bunny'
external_resource_prefix = '/mesh'

class MyRequestHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if self.path.startswith(external_resource_prefix):
            return external_mesh_dir + path[len(external_resource_prefix):]
        else:
            return SimpleHTTPRequestHandler.translate_path(self, path)

httpd = BaseHTTPServer(server_address, MyRequestHandler)
httpd.serve_forever()