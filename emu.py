import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

class EmulatorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
            filepath = 'index.html'
            if os.path.isfile(filepath):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', str(os.path.getsize(filepath)))
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
                return
        
        parsed = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == '/getText.php':
            w_id_list = query_params.get('w_id', [])
            file_list = query_params.get('file', [])
            if not w_id_list:
                self.send_error(400, 'Missing "w_id" parameter')
                return
            if not file_list:
                self.send_error(400, 'Missing "file" parameter')
                return
            w_id = w_id_list[0]
            filename = file_list[0]

            # Защита от path traversal
            safe_w_id = os.path.basename(w_id)
            safe_filename = os.path.basename(filename)
            filepath = os.path.join('texts', safe_w_id, safe_filename)

            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
                # Определяем Content-Type
                content_type = 'text/plain; charset=utf-8' if filepath.endswith('.txt') else 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, f'File {filename} not found in texts/{w_id}/')
            except Exception as e:
                self.send_error(500, f'Server error: {e}')
            return
        if parsed.path == '/getFile.php':
            f_id_list = query_params.get('f_id', [])
            if not f_id_list:
                self.send_error(400, 'Missing "f_id" parameter')
                return
            filename = f_id_list[0]

            # Защита от path traversal
            safe_filename = os.path.basename(filename)
            filepath = os.path.join('files', safe_filename)

            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
                # Определяем Content-Type
                if filepath.endswith('.txt'):
                    content_type = 'text/plain; charset=utf-8'
                else:
                    content_type = 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, f'File {filename} not found in files/')
            except Exception as e:
                self.send_error(500, f'Server error: {e}')
            return
        elif parsed.path == '/lang.php':
            content = 'ru'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == '/version.xml':
            content = '<?xml version="1.0" encoding="UTF-8" ?>\n<VERSION value="бомбом edition"/>'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == '/getAd.php':
            content = 'Здесь могла быть ваша реклама'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == '/getGlav.php':
            content = 'This is not a file'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == '/getWork.php':
            w_id_list = query_params.get('w_id', [])
            if not w_id_list:
                self.send_error(400, 'Missing "w_id" parameter')
                return
            w_id = w_id_list[0]
            safe_w_id = os.path.basename(w_id)
            filepath = os.path.join('works', f'{safe_w_id}.swf')
            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-shockwave-flash')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, f'Work file {w_id}.swf not found')
            except Exception as e:
                self.send_error(500, f'Server error: {e}')
            return
        elif parsed.path == '/getDopuskData.php':
            content = '<ROOT>\n  <TARGET value="Тесты не работают"/>\n  <THEME c1="#FF0000" c2="#00FF00" c3="#0000FF"/>\n  <RESULT value="correct" label="Верно" w_id="task_123" sublink="help/1"/>\n  <FINISH value="true"/>\n  <QUESTION value="Уж извините, оно там защищено"/>\n  <ANSWER id="101" value="Поставить лайк"/>\n  <ANSWER id="102" value="Подписаться"/>\n  <ANSWER id="103" value="Колокольчик"/>\n  <STAT value="Осталось 2 попытки"/>\n  <SCHEME id="bombom"/>\n  <ALLOWED w_id="456"/>\n  <ALLOWED w_id="789"/>\n</ROOT>'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            filepath = parsed.path.lstrip('/')
            if os.path.isfile(filepath):
                self.send_response(200)
                if filepath.endswith('.swf'):
                    self.send_header('Content-Type', 'application/x-shockwave-flash')
                elif filepath.endswith('.html'):
                    self.send_header('Content-Type', 'html')
                else:
                    self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(os.path.getsize(filepath)))
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
                
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/login.php':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            params = urllib.parse.parse_qs(post_data.decode('utf-8'))

            login_list = params.get('login', [])
            if not login_list:
                self.send_error(400, 'Missing "login" parameter')
                return

            login = login_list[0]
            response_body = f"&login0={login}&name0={login}&session=yKHSpdBRi&error=0".encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            return
        elif parsed.path == '/menu.php':
            content = open('menu.xml', 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == '/getStat.php':
            content = open('test_stat.xml', 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(405, 'Method Not Allowed')

if __name__ == '__main__':
    server_address = ('', 6144)
    httpd = HTTPServer(server_address, EmulatorHandler)
    print('Сервер запущен на http://localhost:6144')
    print('Нажми Ctrl+C для остановки.')
    httpd.serve_forever()