import os
import urllib.parse
import secrets
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
import random

TRAINING_MODE = True

# Global storage
user_sessions = {}          # session -> {w_id: current_question_number}
test_answers = {}           # w_id -> {q_key: [correct_answers]}
test_total_q = {}           # w_id -> total_questions
test_files = {}             # w_id -> [sorted_filenames]

# Lab storage
lab_total_q = {}            # w_id -> total_questions
lab_answers = {}            # w_id -> {q_num: correct_answer_string}
lab_files = {}              # w_id -> [sorted_filenames]
lab_attempts = {}           # session -> {w_id: {'q': current_q, 'used': attempts_used}}

MAX_LAB_ATTEMPTS = 5 

# Статистика по тестам: session -> { w_id: { q_num: status } }
# status: None (не отвечен), False (отвечен неправильно), True (отвечен правильно)
test_stats = {}

# Для тренировочного режима: последний выданный вопрос (session -> { w_id: q_num })
user_last_q = {}

LAB_W_IDS = {70, 71, 75, 76, 77, 52, 53, 54, 55, 156, 157, 310, 311, 313, 312, 314,
             296, 297, 298, 299,      474, 477, 475, 478, 484, 485, 487, 486, 458,
             459, 464, 465, 466, 460, 520, 522, 521, 523, 527, 528, 530, 512, 514,
             539, 540, 541, 513, 564, 566, 563, 562, 568, 567, 565, 561, 551, 552,
             545, 547, 304, 233, 66, 203, 204, 205, 206, 207, 208, 209, 210, 67, 68,
             69, 58, 59, 60, 61, 62, 63, 64, 65, 72, 73, 74, 56, 57, 467, 468, 469,
             287, 288, 290, 291, 289, 321, 146, 361, 397, 353, 354, 355, 356, 404,
             362, 403, 395, 357, 359, 358, 360, 402, 425, 408, 399, 410, 585, 571,
             503, 504, 573, 575, 381, 351, 489, 493, 494, 495, 576, 179, 180, 181,
             183, 182, 184, 225, 227, 228, 229, 226, 230}
TEST_W_IDS = {38, 42, 44, 25, 26, 27, 159, 160, 315, 316, 318, 317, 319, 295, 294,
              293, 292, 262, 470, 472, 471, 473, 479, 480, 482, 481, 444, 448, 449,
              450, 451, 447, 453, 454, 455, 456, 457, 452, 516, 518, 517, 519, 524,
              525, 544, 510, 509, 531, 532, 533, 508, 534, 535, 548, 546, 550, 549,
              232, 36, 189, 195, 196, 197, 198, 199, 200, 201, 202, 190, 191, 192,
              193, 194, 37, 30, 31, 32, 33, 34, 35, 39, 40, 41, 28, 29, 461, 462,
              463, 282, 283, 285, 286, 284, 308, 371, 373, 401, 364, 365, 366, 375,
              374, 363, 398, 367, 369, 368, 370, 424, 407, 400, 406, 586, 584, 502,
              501, 572, 574, 352, 490, 496, 580, 581, 497, 175, 176, 185, 178, 177,
              186, 476, 219, 221, 222, 223, 220, 224}


# ========== Вспомогательные функции ==========
def load_test_data(w_id):
    """Загружает ответы и количество вопросов для теста."""
    if w_id in test_total_q:
        return test_total_q[w_id], test_answers.get(w_id, {})

    safe_w_id = os.path.basename(w_id)
    test_dir = os.path.join('tests', safe_w_id)
    if not os.path.isdir(test_dir):
        return None, None

    xml_files = [f for f in os.listdir(test_dir) if f.endswith('.xml')]
    xml_files.sort()
    total_q = len(xml_files)

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
                try:
                    key_int = int(key)
                    key = key_int
                except ValueError:
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

def load_lab_data(w_id):
    """Загружает лабораторную работу (без изменений)."""
    if w_id in lab_total_q:
        return lab_total_q[w_id], lab_answers.get(w_id, {})

    safe_w_id = os.path.basename(w_id)
    lab_dir = os.path.join('labs', safe_w_id)
    if not os.path.isdir(lab_dir):
        return None, None

    xml_files = [f for f in os.listdir(lab_dir) if f.endswith('.xml')]
    xml_files.sort()
    total_q = len(xml_files)

    answers_path = os.path.join(lab_dir, 'answers.txt')
    answers = {}
    if os.path.isfile(answers_path):
        with open(answers_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                try:
                    q_num = int(parts[0])
                except ValueError:
                    continue
                answers[q_num] = parts[1]

    lab_total_q[w_id] = total_q
    lab_answers[w_id] = answers
    lab_files[w_id] = xml_files
    return total_q, answers

def build_question_xml(w_id, q_num, result_value, is_finish, stat_text=None, current_q=None, total_q=None):
    """
    Формирует XML вопроса.
    Если передан stat_text, он используется в поле STAT.
    Иначе формируется стандартная строка "Вопрос X из Y" на основе current_q и total_q.
    """
    safe_w_id = os.path.basename(w_id)
    if w_id not in test_files:
        fallback_path = os.path.join('tests', 'test404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Test not found</ERROR></ROOT>'

    file_list = test_files[w_id]
    if q_num < 1 or q_num > len(file_list):
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

    # RESULT
    result_elem = root.find('RESULT')
    if result_value is None:
        if result_elem is not None:
            root.remove(result_elem)
    else:
        if result_elem is None:
            result_elem = ET.SubElement(root, 'RESULT')
        result_elem.set('value', result_value)
        result_elem.set('label', '')
        result_elem.set('w_id', '0')
        result_elem.set('sublink', '')

    # FINISH
    finish_elem = root.find('FINISH')
    if finish_elem is not None:
        finish_elem.set('value', 'yes' if is_finish else 'no')
    else:
        finish_elem = ET.SubElement(root, 'FINISH')
        finish_elem.set('value', 'yes' if is_finish else 'no')

    # STAT
    stat_elem = root.find('STAT')
    if stat_text:
        stat_value = stat_text
    else:
        stat_value = f'Вопрос {current_q} из {total_q}' if current_q and total_q else ''
    if stat_elem is not None:
        stat_elem.set('value', stat_value)
    else:
        stat_elem = ET.SubElement(root, 'STAT')
        stat_elem.set('value', stat_value)

    return ET.tostring(root, encoding='utf-8')

def build_lab_xml(w_id, q_num, result_value, finish_value, tries_used, max_tries):
    """Формирует XML лабораторной работы (без изменений)."""
    safe_w_id = os.path.basename(w_id)
    if w_id not in lab_files:
        fallback_path = os.path.join('labs', 'lab404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Lab not found</ERROR></ROOT>'

    file_list = lab_files[w_id]
    if q_num < 1 or q_num > len(file_list):
        fallback_path = os.path.join('labs', 'lab404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Question not found</ERROR></ROOT>'

    filename = file_list[q_num - 1]
    filepath = os.path.join('labs', safe_w_id, filename)
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (FileNotFoundError, ET.ParseError):
        fallback_path = os.path.join('labs', 'lab404.xml')
        try:
            with open(fallback_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            return b'<ROOT><ERROR>Lab not found</ERROR></ROOT>'

    trys_elem = root.find('TRYS')
    if trys_elem is not None:
        trys_elem.set('txt', f'{tries_used}/{max_tries}')
    else:
        trys_elem = ET.SubElement(root, 'TRYS')
        trys_elem.set('txt', f'{tries_used}/{max_tries}')

    result_elem = root.find('RESULT')
    if result_value is None:
        if result_elem is not None:
            root.remove(result_elem)
    else:
        if result_elem is None:
            result_elem = ET.SubElement(root, 'RESULT')
        result_elem.set('value', result_value)

    finish_elem = root.find('FINISH')
    if finish_elem is not None:
        finish_elem.set('value', finish_value)
    else:
        finish_elem = ET.SubElement(root, 'FINISH')
        finish_elem.set('value', finish_value)

    return ET.tostring(root, encoding='utf-8')

def get_test_stats(session, w_id, total_q):
    """
    Возвращает (correct_count, answered_count) для данного теста.
    correct_count – количество вопросов, на которые дан правильный ответ.
    answered_count – количество вопросов, на которые дан любой ответ.
    """
    stats_dict = test_stats.setdefault(session, {}).setdefault(w_id, {})
    correct = sum(1 for status in stats_dict.values() if status is True)
    answered = sum(1 for status in stats_dict.values() if status is not None)
    return correct, answered


def update_test_status(session, w_id, q_num, is_correct):
    """Обновляет статус вопроса. Возвращает (был_ли_изменён_статус)."""
    stats_dict = test_stats.setdefault(session, {}).setdefault(w_id, {})
    old_status = stats_dict.get(q_num)
    if is_correct:
        if old_status is not True:
            stats_dict[q_num] = True
            return True   # статус изменился (стал правильным)
    else:
        if old_status is None:
            stats_dict[q_num] = False
            return True   # впервые отвечен неправильно
    return False


# ========== HTTP-обработчик ==========
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
        if parsed.path == '/getBgd.php':
            t_id_list = query_params.get('t_id', [])
            if not t_id_list:
                self.send_error(400, 'Missing "t_id" parameter')
                return
            filename = t_id_list[0]
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
            try:
                w_id_int = int(w_id)
            except ValueError:
                w_id_int = None

            if w_id_int in LAB_W_IDS:
                filename = 'lab.swf'
            elif w_id_int in TEST_W_IDS:
                filename = 'test.swf'
            else:
                filename = f'{safe_w_id}.swf'

            filepath = os.path.join('works', filename)
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
            if not w_id_list or not s_hash_list:
                self.send_error(400, 'Missing "w_id" or "s_hash" parameter')
                return

            w_id = w_id_list[0]
            s_hash = s_hash_list[0]
            answer_str = answer_list[0] if answer_list else None
            answer = int(answer_str) if answer_str is not None and answer_str.isdigit() else None

            if s_hash not in user_sessions:
                self.send_error(400, 'Invalid session')
                return

            total_q, answers = load_test_data(w_id)
            if total_q is None or total_q == 0:
                self.send_error(404, 'No questions found for this test')
                return

            # Инициализация статистики для данного теста
            if s_hash not in test_stats:
                test_stats[s_hash] = {}
            if w_id not in test_stats[s_hash]:
                test_stats[s_hash][w_id] = {}

            # ========== ТРЕНИРОВОЧНЫЙ РЕЖИМ ==========
            if TRAINING_MODE:
                # Получить или сгенерировать текущий вопрос
                if s_hash not in user_last_q:
                    user_last_q[s_hash] = {}
                curr_q = user_last_q[s_hash].get(w_id)
                if curr_q is None or curr_q < 1 or curr_q > total_q:
                    curr_q = random.randint(1, total_q)
                    user_last_q[s_hash][w_id] = curr_q

                # Обработка ответа
                if answer is not None:
                    # Проверяем правильность ответа
                    base_filename = os.path.splitext(test_files[w_id][curr_q - 1])[0]
                    correct_list = answers.get(base_filename) or answers.get(curr_q)
                    is_correct = (correct_list is not None and answer in correct_list)

                    # Обновляем статус вопроса
                    update_test_status(s_hash, w_id, curr_q, is_correct)

                    # Генерируем новый случайный вопрос
                    new_q = random.randint(1, total_q)
                    user_last_q[s_hash][w_id] = new_q
                    curr_q_for_response = new_q
                    is_finish = False
                    result_value = "correct" if is_correct else "wrong"
                else:
                    # Просто отдаём текущий вопрос
                    curr_q_for_response = curr_q
                    is_finish = False
                    result_value = None

                # Подсчёт статистики
                correct_cnt, answered_cnt = get_test_stats(s_hash, w_id, total_q)
                stat_text = f"Верно {correct_cnt} из {answered_cnt}. Всего {total_q}"
                content = build_question_xml(
                    w_id, curr_q_for_response, result_value, is_finish,
                    stat_text=stat_text
                )
                self.send_response(200)
                self.send_header('Content-Type', 'application/xml; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            # ========== ОБЫЧНЫЙ (ПОСЛЕДОВАТЕЛЬНЫЙ) РЕЖИМ ==========
            # Получаем текущий номер вопроса
            user_data = user_sessions[s_hash]
            current_q = user_data.get(w_id, 1)
            if current_q > total_q:
                current_q = total_q

            # Обработка ответа
            if answer is not None:
                # Определяем правильность ответа
                base_filename = os.path.splitext(test_files[w_id][current_q - 1])[0]
                correct_list = answers.get(base_filename) or answers.get(current_q)
                is_correct = (correct_list is not None and answer in correct_list)

                # Обновляем статистику
                update_test_status(s_hash, w_id, current_q, is_correct)

                # Переход к следующему вопросу
                next_q = current_q + 1
                user_data[w_id] = next_q
                send_q = next_q if next_q <= total_q else total_q
                is_finish = (next_q > total_q)
                result_value = "correct" if is_correct else "wrong"

                correct_cnt, answered_cnt = get_test_stats(s_hash, w_id, total_q)
                stat_text = f"Верно {correct_cnt} из {answered_cnt}. Всего {total_q}"
                content = build_question_xml(
                    w_id, send_q, result_value, is_finish,
                    stat_text=stat_text
                )
            else:
                # Просто отдаём текущий вопрос (без ответа)
                is_finish = (current_q == total_q)
                correct_cnt, answered_cnt = get_test_stats(s_hash, w_id, total_q)
                stat_text = f"Верно {correct_cnt} из {answered_cnt}. Всего {total_q}"
                content = build_question_xml(
                    w_id, current_q, None, is_finish,
                    stat_text=stat_text
                )

            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        elif parsed.path == '/getLabData.php':
            w_id_list = query_params.get('w_id', [])
            s_hash_list = query_params.get('s_hash', [])
            if not w_id_list or not s_hash_list:
                try:
                    with open('testLab.xml', 'rb') as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/xml; charset=utf-8')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except FileNotFoundError:
                    self.send_error(404, 'testLab.xml not found')
                return

            w_id = w_id_list[0]
            s_hash = s_hash_list[0]
            if s_hash not in user_sessions:
                self.send_error(400, 'Invalid session')
                return

            total_q, answers = load_lab_data(w_id)
            if total_q is None or total_q == 0:
                self.send_error(404, 'No lab questions found')
                return

            user_data = user_sessions[s_hash]
            current_q = user_data.get(w_id, 1)
            if current_q > total_q:
                current_q = total_q

            if s_hash not in lab_attempts:
                lab_attempts[s_hash] = {}
            lab_state = lab_attempts[s_hash].get(w_id, {'q': current_q, 'used': 0})
            if lab_state['q'] != current_q:
                lab_state = {'q': current_q, 'used': 0}
                lab_attempts[s_hash][w_id] = lab_state

            used = lab_state['used']
            if current_q > total_q:
                finish_value = 'yes'
            elif used >= MAX_LAB_ATTEMPTS:
                finish_value = 'fail'
            else:
                finish_value = 'no'

            content = build_lab_xml(w_id, current_q, None, finish_value, used, MAX_LAB_ATTEMPTS)
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
            # Инициализация структур для статистики и последнего вопроса
            test_stats[session] = {}
            user_last_q[session] = {}

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
        elif parsed.path == '/getLabData.php':
            # POST: check answer for lab work
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                root = ET.fromstring(post_data)
            except ET.ParseError:
                self.send_error(400, 'Invalid XML')
                return

            work_elem = root.find('WORK')
            session_elem = root.find('SESSION')
            answer_elem = root.find('ANSWER')
            if work_elem is None or session_elem is None or answer_elem is None:
                self.send_error(400, 'Missing WORK/SESSION/ANSWER in XML')
                return

            w_id = work_elem.get('id')
            s_hash = session_elem.get('hash')
            user_answer = answer_elem.get('value', '')

            if not w_id or not s_hash:
                self.send_error(400, 'Missing id or hash')
                return

            if s_hash not in user_sessions:
                self.send_error(400, 'Invalid session')
                return

            total_q, answers = load_lab_data(w_id)
            if total_q is None or total_q == 0:
                self.send_error(404, 'No lab questions found')
                return

            user_data = user_sessions[s_hash]
            current_q = user_data.get(w_id, 1)
            if current_q > total_q:
                current_q = total_q

            if s_hash not in lab_attempts:
                lab_attempts[s_hash] = {}
            lab_state = lab_attempts[s_hash].get(w_id, {'q': current_q, 'used': 0})
            if lab_state['q'] != current_q:
                lab_state = {'q': current_q, 'used': 0}
                lab_attempts[s_hash][w_id] = lab_state

            used = lab_state['used']
            if used >= MAX_LAB_ATTEMPTS:
                content = build_lab_xml(w_id, current_q, None, 'fail', used, MAX_LAB_ATTEMPTS)
                self.send_response(200)
                self.send_header('Content-Type', 'application/xml; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            correct_answer_str = answers.get(current_q)
            if correct_answer_str is None:
                self.send_error(500, f'No correct answer defined for question {current_q}')
                return

            if user_answer == correct_answer_str:
                result_value = "correct_answer"
                next_q = current_q + 1
                user_data[w_id] = next_q
                new_used = 0
                finish_value = 'yes' if next_q > total_q else 'no'
                lab_attempts[s_hash][w_id] = {'q': next_q, 'used': new_used}
            else:
                correct_parts = correct_answer_str.split('|')
                user_parts = user_answer.split('|')
                max_len = max(len(correct_parts), len(user_parts))
                result_parts = []
                for i in range(max_len):
                    corr = correct_parts[i] if i < len(correct_parts) else ''
                    user = user_parts[i] if i < len(user_parts) else ''
                    result_parts.append('correct' if corr == user else 'wrong')
                result_value = '#'.join(result_parts)
                used += 1
                finish_value = 'fail' if used >= MAX_LAB_ATTEMPTS else 'no'
                lab_attempts[s_hash][w_id] = {'q': current_q, 'used': used}

            content = build_lab_xml(w_id, current_q, result_value, finish_value, used, MAX_LAB_ATTEMPTS)
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        else:
            self.send_error(405, 'Method Not Allowed')

if __name__ == '__main__':
    server_address = ('', 6144)
    httpd = HTTPServer(server_address, EmulatorHandler)
    print('Сервер запущен на http://localhost:6144')
    print('Нажми Ctrl+C для остановки.')
    httpd.serve_forever()
