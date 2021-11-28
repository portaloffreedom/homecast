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
        def do_HEAD(self) -> None:
            print("HEAD!!!!!")
            print(self.headers)
            start, end = self.get_range(self.headers)
            self.generate_header((start, end, file_size))
            assert False

        def do_GET(self) -> None:
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

            self.generate_header((start, end, file_size))
            self.wfile.write(body)

        def generate_header(self, range: Tuple[int, int, int]):
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(range[2]))
            self.send_header("Content-Range", "bytes %d-%d/%d" % (range[0], range[1], range[2]))
            self.end_headers()

        def do_GET_chunked(self):
            print(f'GET of file {self.path}')
            self.path = filename
            # return http.server.SimpleHTTPRequestHandler.do_GET(self)

            print(f'HEADERS: {self.headers["Range"]}')
            request_start, request_end = self.get_range(self.headers)
            print(f"LENGTH OF BODY {request_end}-{request_start}")
            body = bytes()
            with open(filename, 'rb') as f:
                assert f.seekable()
                file_end = f.seek(0, 2)
                start = f.seek(request_start, 0)
                request_end = min(file_end, request_end)
                # body = f.read(request_end - request_start)
                # print(f"LENGTH OF BODY {request_end}-{request_start}/{len(body)}")
                response_size = request_end - request_start

                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Type", content_type)
                # self.send_header("Content-Length", str(response_size))
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Content-Range", "bytes %d-%d/%d" % (request_start, request_end, file_end))
                self.end_headers()
                self.flush_headers()

                print("RANGE bytes %d-%d/%d" % (request_start, request_end, response_size))
                f.seek(request_start, 0)
                max_chunk_size = 1024*1024*16  # 16MB
                cursor = request_start
                while cursor < request_end:
                    remaining = request_end - cursor
                    chunk_size = min(max_chunk_size, remaining)
                    print(f"RANGE chunk {cursor}-{cursor + chunk_size}/{chunk_size}")
                    body = f.read(chunk_size)
                    print(f"read this amount: {len(body)}")
                    self.wfile.write(bytes(hex(chunk_size)[2:], 'utf-8'))
                    self.wfile.write(b'\r\n')
                    self.wfile.write(body)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                    cursor += chunk_size
                # self.wfile.write(body)
                self.wfile.write(b'0\r\n\r\n')
                print('Finished GET file')

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
