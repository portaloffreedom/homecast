import http.server
import socket
import socketserver
from multiprocessing import Process
from typing import AnyStr


def process_serve(port: int, filename: AnyStr):
    class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            print(f'GET of file {self.path}')
            self.path = filename
            return http.server.SimpleHTTPRequestHandler.do_GET(self)

        def translate_path(self, path):
            # ignore path, always return the same file
            return filename

    handler = MyHttpRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print("Serving at port ", port)
        httpd.serve_forever()


class Server:
    port: int
    filename: AnyStr
    process: Process

    def __init__(self, filename: AnyStr, port: int = 8000):
        self.port = port
        self.filename = filename
        self.process = Process(target=process_serve, args=(self.port, self.filename))

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()
        self.process.join()

    @staticmethod
    def local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))  # connect() for UDP doesn't send packets
        local_ip_address = s.getsockname()[0]
        return local_ip_address

    def serving_url(self) -> AnyStr:
        #return 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
        return f'http://{Server.local_ip()}:{self.port}/{self.filename}'
