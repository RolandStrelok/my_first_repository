import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import re
import csv


# --- Настройка Poppler ---
poppler_path = r'C:\Program Files\poppler-24.08.0\Library\bin'

# --- Настройка DPI ---
original_dpi = 300
new_dpi = 600
scale_factor = new_dpi / original_dpi

# --- Функция для проверки пересечения областей ---
def is_bbox_overlap(bbox1, bbox2):
    return not (bbox1[2] < bbox2[0] or bbox1[0] > bbox2[2] or bbox1[3] < bbox2[1] or bbox1[1] > bbox2[3])

# --- Функция для объединения слов с дефисом/тире ---
def join_hyphenated_words(words):
    joined_words = []
    i = 0
    while i < len(words):
        if i + 1 < len(words) and words[i + 1].startswith('-'):
            joined_words.append(words[i] + words[i + 1])
            i += 2
        else:
            joined_words.append(words[i])
            i += 1
    return joined_words

# --- Функция для масштабирования координат ---
def scale_coords(coords):
    return tuple(int(c * scale_factor) for c in coords)

def has_digits(text):
    return any(char.isdigit() for char in text)

# --- Абсолютный путь к PDF ---
pdf_path = r'C:\Work\Python\Project\Repository\my_first_repository\doc01089520220614124446.pdf' # УКАЖИТЕ АБСОЛЮТНЫЙ ПУТЬ
pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
output_csv_filename = pdf_filename + "_data.csv"

# --- Координаты целевых областей (left, top, right, bottom) ---
key_area_coords = (2200, 500, 2800, 2000) # Ключевая область
area_1_coords = (0, 0, 700, 2480) # Первая область
area_2_coords = (0, 0, 0, 0) # Вторая область

# --- Масштабирование координат ---
key_area_coords = scale_coords(key_area_coords)
area_1_coords = scale_coords(area_1_coords)
area_2_coords = scale_coords(area_2_coords)


recognized_data_per_page = {}

try:
    all_pages = convert_from_path(pdf_path, poppler_path=poppler_path, dpi=new_dpi)

    page_image = all_pages[0]
    page_num = 1

    # --- Получаем разрешение изображения ---
    width, height = page_image.size
    print(f"Разрешение изображения: {width}x{height} пикселей")

    print(f"\nОбработка страницы {page_num}...")

    key_words_list = []
    area1_words_list = []
    area2_words_list = []

    try:
        page_data = pytesseract.image_to_data(page_image, output_type=pytesseract.Output.DICT, lang='rus+eng', config='--psm 3')

        for j in range(len(page_data['text'])):
            word = page_data['text'][j]
            if word.strip():
                cleaned_word = re.sub(r'[^\w\s-]', '', word).strip()
                word_bbox = (page_data['left'][j], page_data['top'][j], page_data['left'][j] + page_data['width'][j], page_data['top'][j] + page_data['height'][j])

                if is_bbox_overlap(word_bbox, key_area_coords):
                    key_words_list.append(cleaned_word)
                elif is_bbox_overlap(word_bbox, area_1_coords):
                    area1_words_list.append(cleaned_word)
                elif is_bbox_overlap(word_bbox, area_2_coords):
                    area2_words_list.append(cleaned_word)

        key_words_list = join_hyphenated_words(key_words_list)
        area1_words_list = join_hyphenated_words(area1_words_list)
        area2_words_list = join_hyphenated_words(area2_words_list)

        # Фильтрация слов с цифрами
        area1_words_list = [word for word in area1_words_list if has_digits(word)]
        area2_words_list = [word for word in area2_words_list if has_digits(word)]

        key_text_for_dict = " ".join(key_words_list) if key_words_list else "NO_KEY_WORD_FOUND"
        if len(key_text_for_dict) > 150:
            key_text_for_dict = key_text_for_dict[:70] + "..." + key_text_for_dict[-70:]


        recognized_data_per_page[page_num] = {
            'key_text': key_text_for_dict,
            'area1_words': area1_words_list,
            'area2_words': area2_words_list
        }


        with open(output_csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            header = ['Page Number', 'Key Text']
            for area_num in range(1, 3):
                header.extend([f"Area {area_num} Word {word_num + 1}" for word_num in range(20)])
            csv_writer.writerow(header)

            row = [page_num, recognized_data_per_page[page_num]['key_text']]
            for area_num in range(1, 3):
                row.extend(recognized_data_per_page[page_num][f'area{area_num}_words'])
            csv_writer.writerow(row)


    except Exception as e:
        print(f"Ошибка обработки страницы {page_num}: {e}")

except Exception as e:
    print(f"Ошибка: {e}")


print("\nОбработка завершена.")
