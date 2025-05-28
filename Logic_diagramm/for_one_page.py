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
recognized_data_per_page = {}

# --- Координаты целевой области для ключа (left, top, right, bottom) ---
key_area_coords = (0, 0, 1000, 200) # <--- ИЗМЕНИТЕ ЭТИ КООРДИНАТЫ ПОД ВАШИ НУЖДЫ!

# --- Настройки для CSV-файла ---
output_csv_filename = 'ocr_results_grouped_highlighted_digits_test.csv' # Изменил имя файла
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
    # re.sub(r'[^\p{L}\p{N}\s-]', '', text, flags=re.UNICODE) - это для более широкого Юникода
    # Для базового ру/англ, '\w' (буквы, цифры, _) и '-' будет достаточно
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
            except (IndexError, TypeError): # Обрабатываем ошибки для очень маленьких сегментов
                pass
            except Exception as e:
                # print(f"Warning: Could not get pixel at ({x},{y}) from segment: {e}")
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
                    # Для проверки выделения, вырезаем сегмент по объединенному bbox
                    if logical_word_bbox[2] > logical_word_bbox[0] and logical_word_bbox[3] > logical_word_bbox[1]:
                        segment = page_image.crop(logical_word_bbox)
                        highlighted_status = is_highlighted(segment)
                    else:
                        highlighted_status = False # Невозможно определить для некорректного bbox

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

        # --- Теперь фильтруем логические слова по условиям ---
        key_words_for_dict = []
        remaining_words_for_dict = []

        # Преобразуем key_area_coords в формат (x_min, y_min, x_max, y_max)
        key_area_bbox = (key_area_coords[0], key_area_coords[1], key_area_coords[2], key_area_coords[3])

        for logical_word_text, logical_word_bbox, is_highlighted_status in logical_words_on_page:
            if contains_digit(logical_word_text) and is_highlighted_status:
                if is_bbox_overlap(logical_word_bbox, key_area_bbox):
                    key_words_for_dict.append(logical_word_text)
                else:
                    remaining_words_for_dict.append(logical_word_text)

        # Формируем ключ для словаря
        key_text_for_dict = ""
        if key_words_for_dict:
            key_text_for_dict = " ".join(key_words_for_dict)
            if len(key_text_for_dict) > 150:
                key_text_for_dict = key_text_for_dict[:70] + "..." + key_text_for_dict[-70:]
        else:
            key_text_for_dict = "NO_MATCHING_KEY_WORD" # Если нет слов, подходящих под критерии для ключа

        # Делаем список оставшихся слов уникальным и сортируем для консистентности
        remaining_words_unique_sorted = list(sorted(set(remaining_words_for_dict)))

        # --- 4. Сохраняем результат в словаре с кортежем в качестве ключа ---
        dictionary_key = (key_text_for_dict, page_num)
        recognized_data_per_page[dictionary_key] = remaining_words_unique_sorted

        print(f"   -> Ключ для страницы {page_num}: '{key_text_for_dict}'")
        print(f"   -> Список оставшихся уникальных логических слов (выделенных с цифрами) для страницы {page_num} создан (найдено {len(remaining_words_unique_sorted)} слов).")

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
    sorted_items = sorted(recognized_data_per_page.items(), key=lambda item: item[0][1])

    for key_tuple, value_list in sorted_items:
        key_text_part, page_num_part = key_tuple
        print(f"\nКлюч (выделенный текст с цифрами) со страницы {page_num_part}: '{key_text_part}'")

        display_words_limit = 20
        display_words = value_list[:display_words_limit]

        print(f"Оставшиеся уникальные выделенные логические слова (с цифрами) на этой странице: {display_words}{'...' if len(value_list) > display_words_limit else ''}")
        print(f"Всего уникальных оставшихся слов (с цифрами) на этой странице: {len(value_list)}")
        print("-" * 60)
else:
    print("Результатов распознавания нет. Возможно, PDF пуст, или произошла ошибка во время обработки.")

# --- Сохранение результатов в CSV файл ---
print(f"\nСохранение результатов в CSV файл: '{output_csv_filename}'")
try:
    with open(output_csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        csv_writer.writerow(['Page Number', 'Key Text (Highlighted, Digits, Grouped)', 'Remaining Unique Words (Highlighted, Digits, Grouped)'])

        sorted_items = sorted(recognized_data_per_page.items(), key=lambda item: item[0][1])
        for key_tuple, value_list in sorted_items:
            key_text_part, page_num_part = key_tuple

            remaining_words_str = words_internal_delimiter.join(value_list)

            csv_writer.writerow([page_num_part, key_text_part, remaining_words_str])
    print(f"Результаты успешно сохранены в '{output_csv_filename}'.")
except IOError as e:
    print(f"Ошибка при сохранении CSV файла: {e}")

print("\nОбработка завершена.")
