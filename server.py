import os
import socket
import http.server
import socketserver
from http import HTTPStatus
from multiprocessing import Process
from typing import AnyStr, Tuple


def generate_content_type(filename: AnyStr) -> AnyStr:
    extension = filename.split('.')[-1]
    if extension == 'mkv':
        extension = 'x-matroska'
    return f'video/{extension}'


def process_serve(port: int, filename: AnyStr):
    file_size: int = os.path.getsize(filename)
    content_type: AnyStr = generate_content_type(filename)

    class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            print(f'GET of file {self.path}')
            self.path = filename
            # return http.server.SimpleHTTPRequestHandler.do_GET(self)

            # print(f'HEADERS: {self.headers}')
            start, end = self.get_range(self.headers)
            body = bytes()
            with open(filename, 'rb') as f:
                f.seek(start)
                body = f.read(end - start)
            end = start + len(body) - 1

            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, file_size))
            self.end_headers()
            self.wfile.write(body)

        def translate_path(self, path):
            # ignore path, always return the same file
            return filename

        def get_range(self, headers) -> Tuple[int, int]:
            start: int = 0
            size: int = file_size
            try:
                rkey = headers['Range']
                if not rkey:
                    raise "no range header"
                unit, range = rkey.split('=')
                if unit != 'bytes':
                    raise "unknown unit"
                s, e = range.split('-')
                start = int(s)
                e = int(e)
                end = e if not e == 0 else start+size
                return start, end
            except:
                return start, start + size


    with http.server.ThreadingHTTPServer(("", port), MyHttpRequestHandler) as httpd:
        # with socketserver.TCPServer(("", port), MyHttpRequestHandler) as httpd:
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

    def content_type(self) -> AnyStr:
        return generate_content_type(self.filename)
