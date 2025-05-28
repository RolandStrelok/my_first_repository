import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import re
import string
import csv
import numpy as np

# --- Настройка путей ---
poppler_path = r'C:\Program Files\poppler-24.08.0\Library\bin'

# --- Путь к вашему PDF-файлу ---
pdf_path = 'C:\Work\Python\Project\Repository\my_first_repository\Logic_diagramm\DCS LOGIC DIAGRAM - AMMONIA UTILITIES.pdf' # <--- ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ НА ВАШ ПОЛНЫЙ ПУТЬ К PDF-ФАЙЛУ!

# --- Словарь для хранения результатов ---
# Структура: { номер_страницы: { 'key_text': '...', 'area1_words': [...], 'area2_words': [...] } }
recognized_data_per_page = {}

# --- Координаты целевых областей (left, top, right, bottom) ---
# Вам нужно определить эти координаты, просмотрев ваш PDF в графическом редакторе
# или программе просмотра PDF (например, XnView MP, Adobe Acrobat Reader, GIMP).
# (X1, Y1, X2, Y2) - верхний левый угол (X1, Y1), нижний правый угол (X2, Y2)

key_area_coords = (0, 0, 1100, 200) # <--- Ключевая область
area_1_coords = (0, 0, 700, 1000)   # <--- Первая новая область (например, левая нижняя)
area_2_coords = (1200, 0, 1920, 1000) # <--- Вторая новая область (например, правая нижняя)

# <--- ИЗМЕНИТЕ ЭТИ КООРДИНАТЫ ПОД ВАШИ НУЖДЫ!

# --- Настройки для CSV-файла ---
output_csv_filename = 'ocr_multi_area_results_test.csv' # Новое имя файла для нескольких областей
words_internal_delimiter = '; ' 

# --- Цветовые диапазоны для маркеров (RGB: (min_R, min_G, min_B), (max_R, max_G, max_B)) ---
# Эти диапазоны нужно настроить под реальные цвета ваших маркеров
HIGHLIGHT_COLOR_RANGES = {
    'yellow': ((200, 200, 0), (255, 255, 100)), # Ярко-желтый
    'green': ((100, 200, 0), (200, 255, 100)), # Ярко-зеленый
    'pink': ((200, 0, 100), (255, 150, 200)), # Розовый/Малиновый
    'blue': ((0, 100, 200), (100, 200, 255)), # Голубой/Синий
    'orange': ((200, 100, 0), (255, 200, 100)), # Оранжевый
}

# --- Пороги для группировки слов ---
# Эти значения могут потребовать настройки в зависимости от вашего документа
# Максимальный горизонтальный пиксельный зазор между словами, чтобы их объединить
# (примерно 2.5 ширины символа, чтобы 3+ пробела считались разделителем)
MAX_SPACE_PIXEL_GAP_FOR_JOINING = 40 # <--- НАСТРОЙТЕ ЭТО ЗНАЧЕНИЕ!
# Максимальное вертикальное отклонение между словами, чтобы считать их на одной линии
LINE_HEIGHT_THRESHOLD = 10 # <--- НАСТРОЙТЕ ЭТО ЗНАЧЕНИЕ!

# --- Вспомогательные функции ---

def contains_digit(word):
    """Проверяет, содержит ли данное слово хотя бы одну цифру."""
    return any(char.isdigit() for char in word)

def extract_and_clean_word_part(text):
    """
    Приводит текст к нижнему регистру, оставляет буквы, цифры, дефисы и пробелы,
    затем возвращает очищенную строку (не список слов).
    Это для частей, которые потом будут объединяться.
    """
    if not text:
        return ""
    text = text.lower()
    # Оставляем только буквы (Unicode), цифры, пробелы и дефисы
    text = re.sub(r'[^\w\s-]', '', text) 
    return text.strip()

def is_pixel_in_color_range(pixel_rgb, min_rgb, max_rgb):
    """Проверяет, попадает ли цвет пикселя в заданный RGB-диапазон."""
    r, g, b = pixel_rgb
    min_r, min_g, min_b = min_rgb
    max_r, max_g, max_b = max_rgb
    return (min_r <= r <= max_r and
            min_g <= g <= max_g and
            min_b <= b <= max_b)

def is_highlighted(image_segment, min_match_percentage=0.5, dark_pixel_threshold=100):
    """
    Определяет, выделен ли сегмент изображения (слово) маркером.
    Проверяет цвета нескольких точек внутри сегмента.
    dark_pixel_threshold: сумма R+G+B. Пиксели ниже этого порога считаются темными (текст).
    """
    if not image_segment or image_segment.width == 0 or image_segment.height == 0:
        return False

    sample_points = [
        (image_segment.width * 0.1, image_segment.height * 0.1),
        (image_segment.width * 0.5, image_segment.height * 0.1),
        (image_segment.width * 0.9, image_segment.height * 0.1),
        (image_segment.width * 0.1, image_segment.height * 0.5),
        (image_segment.width * 0.5, image_segment.height * 0.5), # Центр
        (image_segment.width * 0.9, image_segment.height * 0.5),
        (image_segment.width * 0.1, image_segment.height * 0.9),
        (image_segment.width * 0.5, image_segment.height * 0.9),
        (image_segment.width * 0.9, image_segment.height * 0.9),
    ]

    highlight_matches = 0
    total_non_dark_samples = 0

    for px, py in sample_points:
        x, y = int(px), int(py)
        if 0 <= x < image_segment.width and 0 <= y < image_segment.height:
            try:
                pixel_rgb = image_segment.getpixel((x, y))
                if not isinstance(pixel_rgb, tuple): # Для черно-белых изображений
                    pixel_rgb = (pixel_rgb, pixel_rgb, pixel_rgb) 

                # Если это не слишком темный пиксель (считаем его фоном, а не текстом)
                if sum(pixel_rgb) > dark_pixel_threshold:
                    total_non_dark_samples += 1
                    for (min_r, min_g, min_b), (max_r, max_g, max_b) in HIGHLIGHT_COLOR_RANGES.values():
                        if is_pixel_in_color_range(pixel_rgb, (min_r, min_g, min_b), (max_r, max_g, max_b)):
                            highlight_matches += 1
                            break
            except (IndexError, TypeError): 
                pass
            except Exception as e:
                pass

    if total_non_dark_samples == 0:
        return False

    return (highlight_matches / total_non_dark_samples) >= min_match_percentage

def is_bbox_overlap(bbox1, bbox2):
    """Проверяет, перекрываются ли две ограничивающие рамки."""
    x1_min, y1_min, x1_max, y1_max = bbox1
    x2_min, y2_min, x2_max, y2_max = bbox2

    if x1_min >= x2_max or x2_min >= x1_max:
        return False
    if y1_min >= y2_max or y2_min >= y1_max:
        return False
    return True

print(f"Начинаем обработку PDF: '{pdf_path}'")
print(f"Координаты ключевой области: {key_area_coords}")
print(f"Координаты Области 1: {area_1_coords}")
print(f"Координаты Области 2: {area_2_coords}")
print(f"Макс. пикс. зазор для объединения слов: {MAX_SPACE_PIXEL_GAP_FOR_JOINING}")
print(f"Макс. верт. отклонение для одной линии: {LINE_HEIGHT_THRESHOLD}")
print("-" * 50)

try:
    print(f"Преобразование PDF '{pdf_path}' в изображения...")
    all_pages = convert_from_path(pdf_path, poppler_path=poppler_path)
    print(f"Обнаружено всего {len(all_pages)} страниц.")

    # --- ТЕСТОВЫЙ РЕЖИМ: ОБРАБАТЫВАЕМ ТОЛЬКО ПЕРВЫЕ 10 СТРАНИЦ ---
    num_pages_to_process = 30
    pages_to_iterate = all_pages[:num_pages_to_process]

    print(f"ВНИМАНИЕ: Активирован тестовый режим. Будет обработано только первые {len(pages_to_iterate)} страниц.")
    print("-" * 50)

    # Преобразуем координаты областей в формат (x_min, y_min, x_max, y_max)
    key_area_bbox = (key_area_coords[0], key_area_coords[1], key_area_coords[2], key_area_coords[3])
    area_1_bbox = (area_1_coords[0], area_1_coords[1], area_1_coords[2], area_1_coords[3])
    area_2_bbox = (area_2_coords[0], area_2_coords[1], area_2_coords[2], area_2_coords[3])


    for i, page_image in enumerate(pages_to_iterate):
        page_num = i + 1 # Нумерация страниц начинается с 1
        print(f"\n--- Обработка страницы {page_num} из {len(pages_to_iterate)} ---")

        # Получаем данные о распознанных словах с координатами
        page_data = pytesseract.image_to_data(page_image, output_type=pytesseract.Output.DICT, lang='rus+eng', config='--psm 3')

        # Список для хранения логических слов с их bbox и состоянием выделения
        # Формат: [(logical_word_text, logical_word_bbox, is_highlighted_bool)]
        logical_words_on_page = []

        current_group_text_parts = [] # Части текущего логического слова
        current_group_x_min, current_group_y_min, current_group_x_max, current_group_y_max = (0,0,0,0)

        # Проходим по всем распознанным "элементам" Tesseract
        for j in range(len(page_data['text'])):
            word_text = page_data['text'][j]
            conf = int(page_data['conf'][j])

            # Пропускаем пустые строки или очень низкую уверенность
            if not word_text.strip() or conf <= 50:
                # Если текущая группа не пуста, завершаем ее
                if current_group_text_parts:
                    logical_word = " ".join(current_group_text_parts)
                    logical_word_bbox = (current_group_x_min, current_group_y_min, current_group_x_max, current_group_y_max)

                    # Проверяем, выделено ли это логическое слово
                    if logical_word_bbox[2] > logical_word_bbox[0] and logical_word_bbox[3] > logical_word_bbox[1]:
                        segment = page_image.crop(logical_word_bbox)
                        highlighted_status = is_highlighted(segment)
                    else:
                        highlighted_status = False

                    logical_words_on_page.append((logical_word, logical_word_bbox, highlighted_status))
                    current_group_text_parts = []
                    current_group_x_min, current_group_y_min, current_group_x_max, current_group_y_max = (0,0,0,0)
                continue # Переходим к следующему элементу

            # Получаем координаты текущего слова Tesseract
            x, y, w, h = page_data['left'][j], page_data['top'][j], page_data['width'][j], page_data['height'][j]
            cleaned_word_part = extract_and_clean_word_part(word_text)

            if not cleaned_word_part: # Если очистка удалила все, пропускаем
                continue

            if not current_group_text_parts: # Первая часть нового логического слова
                current_group_text_parts.append(cleaned_word_part)
                current_group_x_min, current_group_y_min = x, y
                current_group_x_max, current_group_y_max = x + w, y + h
            else:
                # Проверяем расстояние и вертикальное смещение
                horizontal_gap = x - current_group_x_max
                vertical_diff = abs(y - current_group_y_min) # или average_height / 2

                if horizontal_gap < MAX_SPACE_PIXEL_GAP_FOR_JOINING and vertical_diff < LINE_HEIGHT_THRESHOLD:
                    # Объединяем слова, если зазор мал и они на одной линии
                    current_group_text_parts.append(cleaned_word_part)
                    current_group_x_max = x + w # Расширяем bbox по x_max
                    current_group_y_min = min(current_group_y_min, y) # Обновляем y_min
                    current_group_y_max = max(current_group_y_max, y + h) # Обновляем y_max
                else:
                    # Иначе, это новое логическое слово. Сохраняем текущую группу
                    logical_word = " ".join(current_group_text_parts)
                    logical_word_bbox = (current_group_x_min, current_group_y_min, current_group_x_max, current_group_y_max)

                    if logical_word_bbox[2] > logical_word_bbox[0] and logical_word_bbox[3] > logical_word_bbox[1]:
                        segment = page_image.crop(logical_word_bbox)
                        highlighted_status = is_highlighted(segment)
                    else:
                        highlighted_status = False

                    logical_words_on_page.append((logical_word, logical_word_bbox, highlighted_status))

                    # Начинаем новую группу
                    current_group_text_parts = [cleaned_word_part]
                    current_group_x_min, current_group_y_min = x, y
                    current_group_x_max, current_group_y_max = x + w, y + h

        # Добавляем последнюю незавершенную группу после цикла
        if current_group_text_parts:
            logical_word = " ".join(current_group_text_parts)
            logical_word_bbox = (current_group_x_min, current_group_y_min, current_group_x_max, current_group_y_max)
            if logical_word_bbox[2] > logical_word_bbox[0] and logical_word_bbox[3] > logical_word_bbox[1]:
                segment = page_image.crop(logical_word_bbox)
                highlighted_status = is_highlighted(segment)
            else:
                highlighted_status = False
            logical_words_on_page.append((logical_word, logical_word_bbox, highlighted_status))

        # --- Теперь фильтруем логические слова по условиям и распределяем по областям ---
        key_words_list = []
        area1_words_list = []
        area2_words_list = []

        for logical_word_text, logical_word_bbox, is_highlighted_status in logical_words_on_page:
            if contains_digit(logical_word_text) and is_highlighted_status:
                if is_bbox_overlap(logical_word_bbox, key_area_bbox):
                    key_words_list.append(logical_word_text)
                elif is_bbox_overlap(logical_word_bbox, area_1_bbox):
                    area1_words_list.append(logical_word_text)
                elif is_bbox_overlap(logical_word_bbox, area_2_bbox):
                    area2_words_list.append(logical_word_text)
                # Слова, не попадающие ни в одну из областей, игнорируются

        # Формируем ключ для словаря (из слов ключевой области)
        key_text_for_dict = ""
        if key_words_list:
            key_text_for_dict = " ".join(key_words_list)
            if len(key_text_for_dict) > 150:
                key_text_for_dict = key_text_for_dict[:70] + "..." + key_text_for_dict[-70:]
        else:
            key_text_for_dict = "NO_MATCHING_KEY_WORD" # Если нет слов, подходящих под критерии для ключа

        # Делаем списки слов уникальными и сортируем для консистентности
        area1_unique_sorted = list(sorted(set(area1_words_list)))
        area2_unique_sorted = list(sorted(set(area2_words_list)))

        # --- 4. Сохраняем результат в словаре ---
        recognized_data_per_page[page_num] = {
            'key_text': key_text_for_dict,
            'area1_words': area1_unique_sorted,
            'area2_words': area2_unique_sorted
        }

        print(f"   -> Ключ для страницы {page_num}: '{key_text_for_dict}'")
        print(f"   -> Найдено {len(area1_unique_sorted)} выделенных слов (с цифрами) в Области 1.")
        print(f"   -> Найдено {len(area2_unique_sorted)} выделенных слов (с цифрами) в Области 2.")

except Exception as e:
    print(f"\nКРИТИЧЕСКАЯ ОШИБКА при обработке PDF: {e}")
    import traceback
    traceback.print_exc() # Вывод полного стека ошибок
    print("Убедитесь, что Tesseract-OCR и Poppler установлены корректно и пути к ним указаны верно.")
    print("Также проверьте, что PDF-файл существует и не поврежден.")


# --- Вывод окончательных результатов в консоль ---
print("\n" + "=" * 60)
print("--- ОКОНЧАТЕЛЬНЫЕ РЕЗУЛЬТАТЫ РАСПОЗНАВАНИЯ В КОНСОЛИ ---")
print("=" * 60)

if recognized_data_per_page:
    # Сортируем по номеру страницы для более удобного просмотра
    sorted_page_nums = sorted(recognized_data_per_page.keys())

    for page_num in sorted_page_nums:
        page_data_dict = recognized_data_per_page[page_num]
        print(f"\n--- Страница {page_num} ---")
        print(f"Ключ (выделенный текст с цифрами): '{page_data_dict['key_text']}'")

        display_words_limit = 20

        display_area1_words = page_data_dict['area1_words'][:display_words_limit]
        print(f"Область 1 (выделенные логические слова с цифрами): {display_area1_words}{'...' if len(page_data_dict['area1_words']) > display_words_limit else ''}")
        print(f"Всего в Области 1: {len(page_data_dict['area1_words'])}")

        display_area2_words = page_data_dict['area2_words'][:display_words_limit]
        print(f"Область 2 (выделенные логические слова с цифрами): {display_area2_words}{'...' if len(page_data_dict['area2_words']) > display_words_limit else ''}")
        print(f"Всего в Области 2: {len(page_data_dict['area2_words'])}")
        print("-" * 60)
else:
    print("Результатов распознавания нет. Возможно, PDF пуст, или произошла ошибка во время обработки.")

# --- Сохранение результатов в CSV файл ---
print(f"\nСохранение результатов в CSV файл: '{output_csv_filename}'")
try:
    with open(output_csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        csv_writer.writerow([
            'Page Number', 
            'Key Text (Highlighted, Digits, Grouped)', 
            'Area 1 Words (Highlighted, Digits, Grouped)', 
            'Area 2 Words (Highlighted, Digits, Grouped)'
        ])

        sorted_page_nums = sorted(recognized_data_per_page.keys())
        for page_num in sorted_page_nums:
            page_data_dict = recognized_data_per_page[page_num]

            # Объединяем списки слов в строки для CSV
            key_text_str = page_data_dict['key_text']
            area1_words_str = words_internal_delimiter.join(page_data_dict['area1_words'])
            area2_words_str = words_internal_delimiter.join(page_data_dict['area2_words'])

            csv_writer.writerow([page_num, key_text_str, area1_words_str, area2_words_str])
    print(f"Результаты успешно сохранены в '{output_csv_filename}'.")
except IOError as e:
    print(f"Ошибка при сохранении CSV файла: {e}")

print("\nОбработка завершена.")
