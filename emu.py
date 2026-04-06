import os
import urllib.parse
import secrets
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

# Global storage
user_sessions = {}          # session -> {w_id: current_question_number}
test_answers = {}           # w_id -> {q_key: [correct_answers]}
test_total_q = {}           # w_id -> total_questions
test_files = {}             # w_id -> [sorted_filenames]

def load_test_data(w_id):
    """Load answers and count questions for a test."""
    if w_id in test_total_q:
        return test_total_q[w_id], test_answers.get(w_id, {})

    safe_w_id = os.path.basename(w_id)
    test_dir = os.path.join('tests', safe_w_id)
    if not os.path.isdir(test_dir):
        return None, None

    # Count questions: files matching *.xml, sort lexicographically
    xml_files = [f for f in os.listdir(test_dir) if f.endswith('.xml')]
    xml_files.sort()  # natural (lexicographic) sort
    total_q = len(xml_files)

    # Parse answers.txt
    answers_path = os.path.join(test_dir, 'answers.txt')
    answers = {}
    if os.path.isfile(answers_path):
        with open(answers_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                key = parts[0]
                # Try to parse key as integer (for backward compatibility)
                try:
                    key_int = int(key)
                    key = key_int
                except ValueError:
                    # keep as string (filename)
                    pass
                try:
                    correct = [int(x) for x in parts[1:]]
                    answers[key] = correct
                except ValueError:
                    continue

    test_total_q[w_id] = total_q
    test_answers[w_id] = answers
    test_files[w_id] = xml_files
    return total_q, answers

def build_question_xml(w_id, q_num, result_value, is_finish, current_q, total_q):
    """Read question XML, modify RESULT, FINISH, STAT, and return as bytes."""
    # q_num is the question index (1-based) corresponding to position in test_files[w_id]
    safe_w_id = os.path.basename(w_id)
    if w_id not in test_files:
        # Fallback: test not loaded or doesn't exist
        fallback_path = os.path.join('tests', 'test404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Test not found</ERROR></ROOT>'
    file_list = test_files[w_id]
    if q_num < 1 or q_num > len(file_list):
        # Invalid question number
        fallback_path = os.path.join('tests', 'test404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Question not found</ERROR></ROOT>'
    filename = file_list[q_num - 1]
    filepath = os.path.join('tests', safe_w_id, filename)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (FileNotFoundError, ET.ParseError):
        fallback_path = os.path.join('tests', 'test404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Test not found</ERROR></ROOT>'

    # Modify RESULT: remove if no result, else set attributes
    result_elem = root.find('RESULT')
    if result_value is None:
        if result_elem is not None:
            root.remove(result_elem)
    else:
        if result_elem is None:
            # Create a RESULT element if missing (shouldn't happen)
            result_elem = ET.SubElement(root, 'RESULT')
        result_elem.set('value', result_value)
        result_elem.set('label', '')
        result_elem.set('w_id', '0')
        result_elem.set('sublink', '')

    # Modify FINISH
    finish_elem = root.find('FINISH')
    if finish_elem is not None:
        finish_elem.set('value', 'yes' if is_finish else 'no')
    else:
        finish_elem = ET.SubElement(root, 'FINISH')
        finish_elem.set('value', 'yes' if is_finish else 'no')

    # Modify STAT
    stat_elem = root.find('STAT')
    if stat_elem is not None:
        stat_elem.set('value', f'Вопрос {current_q} из {total_q}')
    else:
        stat_elem = ET.SubElement(root, 'STAT')
        stat_elem.set('value', f'Вопрос {current_q} из {total_q}')

    # Convert to string (without XML declaration)
    return ET.tostring(root, encoding='utf-8')

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

            safe_w_id = os.path.basename(w_id)
            safe_filename = os.path.basename(filename)
            filepath = os.path.join('texts', safe_w_id, safe_filename)

            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
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

            safe_filename = os.path.basename(filename)
            filepath = os.path.join('files', safe_filename)

            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
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
            return
        elif parsed.path == '/version.xml':
            content = '<?xml version="1.0" encoding="UTF-8" ?>\n<VERSION value="бомбом edition"/>'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        elif parsed.path == '/getAd.php':
            content = 'Здесь могла быть ваша реклама'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        elif parsed.path == '/getGlav.php':
            content = 'This is not a file'.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
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
            w_id_list = query_params.get('w_id', [])
            s_hash_list = query_params.get('s_hash', [])
            answer_list = query_params.get('answer', [])

            if not w_id_list:
                self.send_error(400, 'Missing "w_id" parameter')
                return
            if not s_hash_list:
                self.send_error(400, 'Missing "s_hash" parameter')
                return

            w_id = w_id_list[0]
            s_hash = s_hash_list[0]
            answer_str = answer_list[0] if answer_list else None
            answer = None
            if answer_str is not None:
                try:
                    answer = int(answer_str)
                except ValueError:
                    answer = 0

            # Validate session
            if s_hash not in user_sessions:
                self.send_error(400, 'Invalid session')
                return

            user_data = user_sessions[s_hash]

            # Check if test folder exists, otherwise fallback
            safe_w_id = os.path.basename(w_id)
            test_dir = os.path.join('tests', safe_w_id)
            if not os.path.isdir(test_dir):
                # Fallback: send test404.xml
                fallback_path = os.path.join('tests', 'test404.xml')
                try:
                    with open(fallback_path, 'rb') as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/xml; charset=utf-8')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except FileNotFoundError:
                    self.send_error(404, 'Test not found')
                return

            # Load test data
            total_q, answers = load_test_data(w_id)
            if total_q is None or total_q == 0:
                self.send_error(404, 'No questions found for this test')
                return

            # Get current question number for this test
            current_q = user_data.get(w_id, 1)  # start at 1
            if current_q > total_q:
                # Already finished, send last question with FINISH=true
                current_q = total_q

            # Determine current filename
            file_list = test_files[w_id]
            current_filename = file_list[current_q - 1]
            # Get base name without extension for lookup
            base_filename = os.path.splitext(current_filename)[0]

            # Process answer if provided and non-zero
            result_value = None
            if answer is not None:
                # Try to get correct answers: first by filename, then by index
                correct = answers.get(base_filename)
                if correct is None:
                    # Fallback to numeric index (1-based)
                    correct = answers.get(current_q)
                if answer in (correct or []):
                    result_value = "correct"
                else:
                    result_value = "wrong"
                # Move to next question
                next_q = current_q + 1
                user_data[w_id] = next_q
                # Determine which question to send
                send_q = next_q if next_q <= total_q else total_q
                is_finish = (next_q > total_q)
                # Build XML for send_q with result
                content = build_question_xml(w_id, send_q, result_value, is_finish, send_q, total_q)
            else:
                # No answer (or answer=0): send current question without result
                is_finish = (current_q == total_q)
                content = build_question_xml(w_id, current_q, None, is_finish, current_q, total_q)

            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        else:
            filepath = parsed.path.lstrip('/')
            if os.path.isfile(filepath):
                self.send_response(200)
                if filepath.endswith('.swf'):
                    self.send_header('Content-Type', 'application/x-shockwave-flash')
                elif filepath.endswith('.swd'):
                    self.send_header('Content-Type', 'application/x-shockwave-flash')
                elif filepath.endswith('.html'):
                    self.send_header('Content-Type', 'text/html')
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
            session = secrets.token_hex(4)
            user_sessions[session] = {}

            response_body = f"&login0={login}&name0={login}&session={session}&error=0".encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            return

        elif parsed.path == '/menu.php':
            try:
                with open('menu.xml', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/xml; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, 'menu.xml not found')
            return

        elif parsed.path == '/getStat.php':
            try:
                with open('test_stat.xml', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, 'test_stat.xml not found')
            return

        else:
            self.send_error(405, 'Method Not Allowed')

if __name__ == '__main__':
    server_address = ('', 6144)
    httpd = HTTPServer(server_address, EmulatorHandler)
    print('Сервер запущен на http://localhost:6144')
    print('Нажми Ctrl+C для остановки.')
    httpd.serve_forever()
